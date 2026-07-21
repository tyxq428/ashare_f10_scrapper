from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ashare_f10.api.jobs_v2 import JobManager
from ashare_f10.config import settings
from ashare_f10.cross_validation.runner import run_full_cross_validation

router = APIRouter(prefix="/api/cross-validation", tags=["cross-validation"])
_manager = JobManager(settings)
_lock = threading.RLock()
_tasks: dict[str, dict[str, Any]] = {}


class FullValidationRequest(BaseModel):
    stock_code: str = Field(pattern=r"^\d{6}$")
    eastmoney_job_id: str | None = None
    max_periods: int | None = Field(default=None, ge=2, le=80)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _task_root(stock_code: str, task_id: str) -> Path:
    return settings.data_dir / stock_code / "cross_validation" / task_id


def _task_state_dir() -> Path:
    path = settings.data_dir / "_cross_validation_tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _task_path(task_id: str) -> Path:
    return _task_state_dir() / f"{task_id}.json"


def _save_task(task: dict[str, Any]) -> None:
    path = _task_path(str(task["task_id"]))
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _update_task(task_id: str, **values: Any) -> dict[str, Any]:
    with _lock:
        task = _tasks[task_id]
        task.update(values, updated_at_utc=_now())
        _save_task(task)
        return dict(task)


def _load_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        if task_id in _tasks:
            return dict(_tasks[task_id])
        path = _task_path(task_id)
        if not path.exists():
            return None
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if task.get("status") in {"PENDING", "RUNNING"}:
            task.update(
                status="INTERRUPTED",
                stage="INTERRUPTED",
                error="服务重启后后台线程已结束；可重新创建任务并复用东方财富与官方文件缓存",
                updated_at_utc=_now(),
            )
            _save_task(task)
        _tasks[task_id] = task
        return dict(task)


def _run_task(task_id: str, request: FullValidationRequest) -> None:
    _update_task(task_id, status="RUNNING", stage="EASTMONEY", started_at_utc=_now())
    try:
        if request.eastmoney_job_id:
            state = _manager.get(request.eastmoney_job_id)
            if not state or state.stock_code != request.stock_code:
                raise LookupError("指定的东方财富任务不存在或股票代码不匹配")
        else:
            pointer = _manager.latest(request.stock_code)
            state = _manager.get(str(pointer.get("job_id"))) if pointer else None
            if state is None:
                state = _manager.create(request.stock_code, resume=True)
                while True:
                    threading.Event().wait(2)
                    refreshed = _manager.get(state.job_id)
                    if refreshed is None:
                        raise RuntimeError("东方财富任务状态丢失")
                    state = refreshed
                    _update_task(
                        task_id,
                        stage="EASTMONEY",
                        eastmoney_job_id=state.job_id,
                        eastmoney_status=state.status,
                        eastmoney_completed_groups=state.completed_groups,
                        eastmoney_total_groups=state.total_groups,
                        eastmoney_failed_groups=state.failed_groups,
                    )
                    if state.status in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED"}:
                        break
        if state.status != "COMPLETED" or state.failed_groups:
            raise RuntimeError(f"东方财富任务未完整成功：{state.status}，失败组{state.failed_groups}")

        _update_task(task_id, stage="OFFICIAL_DISCLOSURE", eastmoney_job_id=state.job_id)
        output = _task_root(request.stock_code, task_id)

        def on_validation_progress(event: dict[str, Any]) -> None:
            stage = str(event.get("stage") or "OFFICIAL_DISCLOSURE")
            details = {key: value for key, value in event.items() if key != "stage"}
            _update_task(task_id, stage=stage, validation_progress=details)

        result = run_full_cross_validation(
            request.stock_code,
            Path(state.output_dir),
            output,
            max_periods=request.max_periods,
            progress=on_validation_progress,
        )
        _update_task(
            task_id,
            status="COMPLETED",
            stage="COMPLETED",
            completed_at_utc=_now(),
            summary=result,
            output_dir=str(output),
            artifacts=result.get("artifacts", {}),
        )
    except Exception as exc:  # noqa: BLE001
        _update_task(
            task_id,
            status="FAILED",
            stage="FAILED",
            completed_at_utc=_now(),
            error=str(exc),
        )


@router.post("/jobs")
def create_full_validation(request: FullValidationRequest) -> dict[str, Any]:
    task_id = uuid.uuid4().hex[:16]
    task = {
        "task_id": task_id,
        "stock_code": request.stock_code,
        "status": "PENDING",
        "stage": "PENDING",
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "max_periods": request.max_periods,
        "eastmoney_job_id": request.eastmoney_job_id,
    }
    with _lock:
        _tasks[task_id] = task
        _save_task(task)
    threading.Thread(target=_run_task, args=(task_id, request), daemon=True).start()
    return dict(task)


@router.get("/jobs/{task_id}")
def get_full_validation(task_id: str) -> dict[str, Any]:
    task = _load_task(task_id)
    if task is not None:
        return task
    raise HTTPException(status_code=404, detail="交叉验证任务不存在")


@router.get("/jobs/{task_id}/comparison")
def comparison_rows(
    task_id: str,
    q: str = "",
    status: str | None = None,
    validation_mode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    task = get_full_validation(task_id)
    if task.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="任务尚未完成")
    db_path = Path(task["artifacts"]["comparison_duckdb"])
    conditions = ["1=1"]
    params: list[Any] = []
    if q.strip():
        conditions.append("(field_key ILIKE ? OR field_name_cn ILIKE ? OR family ILIKE ? OR notes ILIKE ?)")
        pattern = f"%{q.strip()}%"
        params.extend([pattern, pattern, pattern, pattern])
    if status:
        conditions.append("status=?")
        params.append(status)
    if validation_mode:
        conditions.append("validation_mode=?")
        params.append(validation_mode)
    if start_date:
        conditions.append("coalesce(report_date,event_date)>=?")
        params.append(start_date)
    if end_date:
        conditions.append("coalesce(report_date,event_date)<=?")
        params.append(end_date)
    where = " AND ".join(conditions)
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        total = int(
            connection.execute(f"SELECT count(*) FROM reconciliation WHERE {where}", params).fetchone()[0]
        )
        rows = (
            connection.execute(
                f"SELECT * FROM reconciliation WHERE {where} ORDER BY report_date DESC NULLS LAST, field_name_cn LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
            .fetchdf()
            .to_dict("records")
        )
    finally:
        connection.close()
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


@router.get("/jobs/{task_id}/coverage")
def coverage(task_id: str) -> dict[str, Any]:
    task = get_full_validation(task_id)
    if task.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="任务尚未完成")
    summary = task.get("summary") or {}
    return {
        key: summary.get(key)
        for key in (
            "classification_coverage",
            "unique_field_contexts",
            "classified_field_contexts",
            "mode_counts",
            "status_counts",
            "true_conflict_count",
            "comparable_match_rate",
            "acceptance_status",
            "official_source_status",
        )
    }


@router.get("/jobs/{task_id}/evidence/{comparison_key:path}")
def evidence(task_id: str, comparison_key: str) -> dict[str, Any]:
    task = get_full_validation(task_id)
    if task.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="任务尚未完成")
    db_path = Path(task["artifacts"]["comparison_duckdb"])
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        frame = connection.execute(
            "SELECT * FROM reconciliation WHERE comparison_key=? LIMIT 1",
            [comparison_key],
        ).fetchdf()
    finally:
        connection.close()
    if frame.empty:
        raise HTTPException(status_code=404, detail="证据记录不存在")
    return json.loads(frame.to_json(orient="records", force_ascii=False))[0]


@router.get("/jobs/{task_id}/download/{kind}")
def download(task_id: str, kind: str) -> FileResponse:
    task = get_full_validation(task_id)
    artifacts = task.get("artifacts") or {}
    aliases = {
        "comparison_xlsx": "comparison_excel",
        "comparison_db": "comparison_duckdb",
        "official_xlsx": "official_excel",
        "eastmoney_xlsx": "eastmoney_excel",
        "evidence": "evidence_zip",
    }
    key = aliases.get(kind, kind)
    value = artifacts.get(key)
    if not value:
        raise HTTPException(status_code=404, detail=f"没有{kind}文件")
    path = Path(value)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name)
