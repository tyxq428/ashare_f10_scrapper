from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ashare_f10.api.jobs import JobManager
from ashare_f10.api.search import (
    export_search_rows,
    facet_facts,
    list_fields,
    list_periods,
    overview,
    query_facts,
    search_facts,
)
from ashare_f10.calculate.formula import FormulaError, evaluate_formula
from ashare_f10.calculate.ttm import compute_ttm
from ashare_f10.config import settings
from ashare_f10.models import (
    FormulaRequest,
    SearchExportRequest,
    SearchFacetRequest,
    SearchQueryRequest,
    TTMRequest,
)


class CreateJobRequest(BaseModel):
    stock_code: str
    resume: bool = True


class SetCurrentRequest(BaseModel):
    allow_partial: bool = False


app = FastAPI(
    title="A股F10投研平台",
    version="0.3.0",
    description="A-share F10 collection, task recovery, Excel-style filtering, chained search, TTM and formula platform",
)
manager = JobManager(settings)


def latest_paths(stock_code: str) -> tuple[dict[str, Any], Path]:
    pointer = manager.latest(stock_code)
    if not pointer:
        raise HTTPException(status_code=404, detail="尚未找到该股票的完整当前数据版本")
    output_dir = Path(pointer["output_dir"])
    db_path = Path(pointer["artifacts"].get("duckdb", output_dir / "normalized/f10.duckdb"))
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="DuckDB数据文件不存在")
    return pointer, db_path


def job_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (LookupError, FileNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": app.version, "data_dir": str(settings.data_dir)}


@app.post("/api/jobs")
def create_job(request: CreateJobRequest) -> dict[str, Any]:
    try:
        state = manager.create(request.stock_code, resume=request.resume)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return state.model_dump()


@app.get("/api/jobs")
def list_jobs(
    q: str = "",
    status: str | None = None,
    sort_by: str = "created_at_utc",
    sort_direction: str = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    items, total = manager.query_jobs(
        q=q,
        status=status,
        sort_by=sort_by,
        sort_direction=sort_direction,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [state.model_dump() for state in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    state = manager.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state.model_dump()


@app.get("/api/jobs/{job_id}/groups")
def get_job_groups(
    job_id: str,
    status: str | None = None,
    q: str = "",
    theme: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    try:
        items, total = manager.list_groups(job_id, status=status, q=q, theme=theme, offset=offset, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.post("/api/jobs/{job_id}/groups/{group_id}/retry")
def retry_job_group(job_id: str, group_id: str) -> dict[str, Any]:
    try:
        return manager.retry_group(job_id, group_id).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc


@app.post("/api/jobs/{job_id}/retry-failed")
def retry_failed_job_groups(job_id: str) -> dict[str, Any]:
    try:
        return manager.retry_failed(job_id).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc


@app.post("/api/jobs/{job_id}/rerun")
def rerun_job(job_id: str) -> dict[str, Any]:
    try:
        return manager.rerun(job_id).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc


@app.post("/api/jobs/{job_id}/set-current")
def set_current_job(job_id: str, request: SetCurrentRequest) -> dict[str, Any]:
    try:
        return manager.set_current(job_id, allow_partial=request.allow_partial).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="任务不存在或已结束")
    return {"job_id": job_id, "cancel_requested": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, confirm: str = Query(..., min_length=6)) -> dict[str, Any]:
    try:
        return manager.delete(job_id, confirm=confirm)
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc


@app.get("/api/jobs/{job_id}/download/{kind}")
def download_job_artifact(job_id: str, kind: str) -> FileResponse:
    try:
        path = manager.artifact_path(job_id, kind)
    except Exception as exc:  # noqa: BLE001
        raise job_error(exc) from exc
    return FileResponse(path, filename=path.name)


@app.get("/api/stocks/{stock_code}/latest")
def get_latest(stock_code: str) -> dict[str, Any]:
    pointer, db_path = latest_paths(stock_code)
    return {"pointer": pointer, "overview": overview(db_path)}


@app.get("/api/stocks/{stock_code}/search")
def search_stock(
    stock_code: str,
    q: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    theme: str | None = None,
    family: str | None = None,
    numeric_min: float | None = None,
    numeric_max: float | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    """Backward-compatible simple search endpoint."""
    _, db_path = latest_paths(stock_code)
    try:
        return search_facts(
            db_path,
            query=q,
            start_date=start_date,
            end_date=end_date,
            theme=theme,
            family=family,
            numeric_min=numeric_min,
            numeric_max=numeric_max,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stocks/{stock_code}/search/query")
def structured_search(stock_code: str, request: SearchQueryRequest) -> dict[str, Any]:
    """Excel-style column filters, chained secondary search, sorting and pagination."""
    _, db_path = latest_paths(stock_code)
    try:
        return query_facts(db_path, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stocks/{stock_code}/search/facets")
def search_facets(stock_code: str, request: SearchFacetRequest) -> dict[str, Any]:
    """Return unique values/counts for one filter column under the other active conditions."""
    _, db_path = latest_paths(stock_code)
    try:
        return facet_facts(db_path, request.query, request.column, request.term, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stocks/{stock_code}/search/export")
def export_search(stock_code: str, request: SearchExportRequest) -> Response:
    """Export the complete currently filtered result set rather than only the visible page."""
    _, db_path = latest_paths(stock_code)
    try:
        content, media_type, filename = export_search_rows(
            db_path,
            request.query,
            output_format=request.format,
            max_rows=request.max_rows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/stocks/{stock_code}/fields")
def get_fields(stock_code: str, q: str = "", limit: int = Query(200, ge=1, le=1000)) -> list[dict[str, Any]]:
    _, db_path = latest_paths(stock_code)
    return list_fields(db_path, q, limit)


@app.get("/api/stocks/{stock_code}/periods")
def get_periods(stock_code: str) -> list[str]:
    _, db_path = latest_paths(stock_code)
    return list_periods(db_path)


@app.post("/api/stocks/{stock_code}/ttm")
def calculate_ttm(stock_code: str, request: TTMRequest) -> dict[str, Any]:
    _, db_path = latest_paths(stock_code)
    try:
        result = compute_ttm(db_path, request.field, request.end_period)
        return {
            **result.__dict__,
            "components": [component.__dict__ for component in result.components],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stocks/{stock_code}/formula")
def calculate_formula(stock_code: str, request: FormulaRequest) -> dict[str, Any]:
    _, db_path = latest_paths(stock_code)
    try:
        return evaluate_formula(db_path, request.formula, request.end_period)
    except (FormulaError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/stocks/{stock_code}/download/{kind}")
def download(stock_code: str, kind: str) -> FileResponse:
    pointer, _ = latest_paths(stock_code)
    artifacts = pointer.get("artifacts", {})
    aliases = {"xlsx": "excel", "db": "duckdb"}
    artifact_key = aliases.get(kind, kind)
    path_value = artifacts.get(artifact_key)
    if not path_value:
        raise HTTPException(status_code=404, detail=f"没有{kind}文件")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name)


# Package the lightweight SPA with the Python distribution. The same files are usable by GitHub Pages.
_web_resource = files("ashare_f10").joinpath("web")
_web_context = as_file(_web_resource)
_web_path = _web_context.__enter__()
app.mount("/", StaticFiles(directory=str(_web_path), html=True), name="web")
