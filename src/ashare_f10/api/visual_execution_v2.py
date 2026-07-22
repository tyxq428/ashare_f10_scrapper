from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ashare_f10.api.visual_jobs_v2 import (
    DEFAULT_VISUAL_OPTIONS,
    OFFICIAL_VALIDATION_SCOPES,
    VisualJobManager,
    normalize_visual_options,
)
from ashare_f10.config import settings

router = APIRouter(prefix="/api/visual-execution", tags=["visual-execution"])
manager = VisualJobManager(settings)

OfficialValidationScope = Literal["latest", "recent_3y", "recent_5y", "full_history"]


class VisualJobRequest(BaseModel):
    stock_code: str
    resume: bool = True
    workers: int = Field(default=8, ge=1, le=32)
    auto_retry_failed: bool = True
    max_auto_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: int = Field(default=5, ge=0, le=120)
    include_raw_pack: bool = False
    raw_pack_packs: str = "default"
    raw_pack_max_docs: int = Field(default=200, ge=1, le=5000)
    run_official_validation: bool = False
    official_validation_scope: OfficialValidationScope = "full_history"
    # Backward-compatible request fields. The visual UI no longer exposes them.
    official_annual_year: int = Field(default=2025, ge=2000, le=2100)
    official_quarter_year: int = Field(default=2026, ge=2000, le=2100)

    def execution_options(self) -> dict[str, Any]:
        payload = self.model_dump(exclude={"stock_code", "resume"})
        return normalize_visual_options(payload)


def _job_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (LookupError, FileNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/capabilities")
def visual_capabilities() -> dict[str, Any]:
    return {
        "defaults": DEFAULT_VISUAL_OPTIONS,
        "presets": [
            {
                "id": "f10",
                "label": "快速结构化",
                "description": "只生成F10 JSON、Excel、Parquet和DuckDB，速度最快。",
                "include_raw_pack": False,
                "run_official_validation": False,
            },
            {
                "id": "f10_raw_pack",
                "label": "官方资料收集",
                "description": "F10完成后自动收集交易所原文、公司官网、IR和权限状态证据。",
                "include_raw_pack": True,
                "run_official_validation": False,
            },
            {
                "id": "f10_official",
                "label": "全历史官方验证",
                "description": "自动识别上市日期，下载所选范围内的全部官方报告并与F10对账。",
                "include_raw_pack": False,
                "run_official_validation": True,
            },
            {
                "id": "full_research",
                "label": "深度研究（推荐）",
                "description": "F10、Raw Pack与官方全历史验证；F10完成后后两项并行执行。",
                "include_raw_pack": True,
                "run_official_validation": True,
            },
        ],
        "official_validation_scopes": [
            {"value": key, **value} for key, value in OFFICIAL_VALIDATION_SCOPES.items()
        ],
        "raw_pack_packs": [
            {"value": "default", "label": "默认核心来源"},
            {"value": "all", "label": "全部已实现来源"},
            {"value": "P0_STATUTORY_CORE", "label": "仅法定披露"},
            {"value": "P1_IP_PRODUCT_TECH", "label": "仅官网/IP/IR"},
            {"value": "P1_ENTITY_RISK_CORE", "label": "仅实体风险探测"},
        ],
        "status_contract": {
            "core_job": [
                "PENDING",
                "RUNNING",
                "RETRYING",
                "PARTIAL",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
            ],
            "optional_stages": [
                "NOT_REQUESTED",
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "COMPLETED_WITH_REVIEW",
                "FAILED",
                "SKIPPED_INCOMPLETE_F10",
            ],
        },
    }


@router.post("/jobs")
def create_visual_job(request: VisualJobRequest) -> dict[str, Any]:
    try:
        state = manager.create_visual(
            request.stock_code,
            resume=request.resume,
            options=request.execution_options(),
        )
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return manager.visual_payload(state)


@router.get("/jobs")
def list_visual_jobs(
    q: str = "",
    status: str | None = None,
    sort_by: str = "created_at_utc",
    sort_direction: str = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    states, total = manager.query_jobs(
        q=q,
        status=status,
        sort_by=sort_by,
        sort_direction=sort_direction,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [manager.visual_payload(state) for state in states],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/jobs/{job_id}")
def get_visual_job(job_id: str) -> dict[str, Any]:
    state = manager.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return manager.visual_payload(state)


@router.get("/jobs/{job_id}/groups")
def get_visual_job_groups(
    job_id: str,
    status: str | None = None,
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    try:
        items, total = manager.list_groups(
            job_id,
            status=status,
            q=q,
            offset=offset,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/jobs/{job_id}/retry-failed")
def retry_visual_failed(job_id: str) -> dict[str, Any]:
    try:
        state = manager.retry_failed(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return manager.visual_payload(state)


@router.post("/jobs/{job_id}/rerun")
def rerun_visual_job(job_id: str) -> dict[str, Any]:
    try:
        state = manager.rerun_visual(job_id)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return manager.visual_payload(state)


@router.post("/jobs/{job_id}/cancel")
def cancel_visual_job(job_id: str) -> dict[str, Any]:
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="任务不存在或已经结束")
    return {"job_id": job_id, "cancel_requested": True}


@router.get("/jobs/{job_id}/download/{kind}")
def download_visual_artifact(job_id: str, kind: str) -> FileResponse:
    try:
        path = manager.artifact_path(job_id, kind)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="该Artifact不是可直接下载的文件")
    return FileResponse(path, filename=path.name)


__all__ = ["VisualJobRequest", "manager", "router", "visual_capabilities"]
