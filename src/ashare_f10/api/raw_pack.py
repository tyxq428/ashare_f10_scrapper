from __future__ import annotations

import json
import threading
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ashare_f10.config import settings

router = APIRouter(prefix="/api/raw-pack", tags=["raw-pack"])
_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


class RawPackJobRequest(BaseModel):
    stock_code: str
    packs: str = "default"
    max_docs: int = Field(default=200, ge=1, le=5000)


class ManualEvidenceRequest(BaseModel):
    stock_code: str
    source_id: str
    title: str
    source_url: str
    notes: str = ""
    local_file_path: str | None = None


def _latest_f10_output(stock_code: str) -> Path:
    pointer_path = settings.data_dir / stock_code / "latest.json"
    if not pointer_path.exists():
        raise FileNotFoundError("尚无该股票的完整F10版本，请先运行F10任务")
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    output_dir = Path(payload["output_dir"])
    if not output_dir.exists():
        raise FileNotFoundError("F10最新版本目录不存在")
    return output_dir


def _latest_raw_pack_pointer(stock_code: str) -> dict[str, Any]:
    output_dir = _latest_f10_output(stock_code)
    pointer = output_dir / "raw_pack" / stock_code / "latest.json"
    if not pointer.exists():
        raise FileNotFoundError("尚无该股票的Raw Pack版本")
    return json.loads(pointer.read_text(encoding="utf-8"))


def _documents(stock_code: str) -> list[dict[str, Any]]:
    pointer = _latest_raw_pack_pointer(stock_code)
    path = Path(pointer["source_documents_jsonl"])
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _run_job(job_id: str, request: RawPackJobRequest) -> None:
    with _LOCK:
        _JOBS[job_id].update(status="RUNNING", message="正在生成官方Raw Pack")
    try:
        from ashare_f10.raw_sources.runner import run_raw_pack

        f10_dir = _latest_f10_output(request.stock_code)
        result = run_raw_pack(
            request.stock_code,
            f10_dir,
            f10_run_dir=f10_dir,
            packs=request.packs,
            max_docs=request.max_docs,
        )
        with _LOCK:
            _JOBS[job_id].update(
                status="COMPLETED",
                message="Raw Pack完成",
                result=result,
                output_dir=result["output_dir"],
            )
    except Exception as exc:  # noqa: BLE001
        with _LOCK:
            _JOBS[job_id].update(status="FAILED", message=str(exc), error=f"{type(exc).__name__}: {exc}")


@router.post("/jobs")
def create_raw_pack_job(request: RawPackJobRequest) -> dict[str, Any]:
    try:
        _latest_f10_output(request.stock_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job_id = f"raw-{request.stock_code}-{uuid.uuid4().hex[:10]}"
    state = {
        "job_id": job_id,
        "stock_code": request.stock_code,
        "packs": request.packs,
        "max_docs": request.max_docs,
        "status": "PENDING",
        "message": "任务已创建",
    }
    with _LOCK:
        _JOBS[job_id] = state
    threading.Thread(target=_run_job, args=(job_id, request), daemon=True).start()
    return state


@router.get("/jobs")
def list_raw_pack_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        return list(reversed(list(_JOBS.values())))


@router.get("/jobs/{job_id}")
def get_raw_pack_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _JOBS.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Raw Pack任务不存在")
    return state


@router.get("/jobs/{job_id}/artifacts")
def get_raw_pack_job_artifacts(job_id: str) -> dict[str, Any]:
    state = get_raw_pack_job(job_id)
    result = state.get("result") or {}
    if state.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="Raw Pack任务尚未完成")
    return result.get("artifacts", {})


@router.get("/evidence/search")
def search_raw_pack_evidence(
    stock_code: str,
    q: str = "",
    status: str | None = None,
    source_tier: str | None = None,
    pack_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        rows = _documents(stock_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    needle = q.strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if status and row.get("status") != status:
            continue
        if source_tier and row.get("source_tier") != source_tier:
            continue
        if pack_id and row.get("pack_id") != pack_id:
            continue
        date_value = row.get("publish_date") or row.get("report_period") or row.get("retrieved_at_utc") or ""
        if start_date and str(date_value)[:10] < start_date:
            continue
        if end_date and str(date_value)[:10] > end_date:
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in (
                "document_title",
                "source_url",
                "source_organization",
                "source_id",
                "pack_id",
                "status",
                "notes",
            )
        ).lower()
        if needle and needle not in haystack:
            parsed_path = row.get("parsed_text_path")
            if not parsed_path or not Path(parsed_path).exists():
                continue
            if needle not in Path(parsed_path).read_text(encoding="utf-8", errors="ignore").lower():
                continue
        filtered.append(row)
    total = len(filtered)
    return {"rows": filtered[offset : offset + limit], "total": total, "offset": offset, "limit": limit}


@router.get("/evidence/stats")
def raw_pack_evidence_stats(stock_code: str) -> dict[str, Any]:
    try:
        rows = _documents(stock_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "document_count": len(rows),
        "status_counts": dict(Counter(row.get("status") for row in rows)),
        "source_tier_counts": dict(Counter(row.get("source_tier") for row in rows)),
        "pack_counts": dict(Counter(row.get("pack_id") for row in rows)),
        "downloaded_file_count": sum(bool(row.get("raw_original_binary_saved")) for row in rows),
        "parsed_text_count": sum(bool(row.get("parsed_text_saved")) for row in rows),
    }


@router.get("/documents/{document_id}")
def get_raw_pack_document(document_id: str, stock_code: str) -> dict[str, Any]:
    try:
        rows = _documents(stock_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for row in rows:
        if row.get("document_id") == document_id:
            text = ""
            path = row.get("parsed_text_path")
            if path and Path(path).exists():
                text = Path(path).read_text(encoding="utf-8", errors="ignore")[:200_000]
            return {"document": row, "text": text}
    raise HTTPException(status_code=404, detail="Raw Pack文档不存在")


@router.get("/documents/{document_id}/download")
def download_raw_pack_document(document_id: str, stock_code: str) -> FileResponse:
    payload = get_raw_pack_document(document_id, stock_code)
    path_value = payload["document"].get("original_file_path")
    if not path_value:
        raise HTTPException(status_code=404, detail="该记录没有已保存的原始文件")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=404, detail="原始文件不存在")
    return FileResponse(path, filename=path.name)


@router.get("/blocked")
def list_blocked_sources(stock_code: str) -> list[dict[str, Any]]:
    try:
        return [row for row in _documents(stock_code) if row.get("status") == "PERMISSION_BLOCKED"]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-evidence")
def register_manual_evidence(request: ManualEvidenceRequest) -> dict[str, Any]:
    output_dir = _latest_f10_output(request.stock_code)
    target_dir = output_dir / "raw_pack" / request.stock_code / "manual_evidence"
    target_dir.mkdir(parents=True, exist_ok=True)
    record = request.model_dump(mode="json")
    record["registered_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    path = target_dir / f"{request.source_id}-{uuid.uuid4().hex[:10]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "REGISTERED", "record_path": str(path)}
