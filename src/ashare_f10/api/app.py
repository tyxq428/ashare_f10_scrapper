from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ashare_f10.api.jobs import JobManager
from ashare_f10.api.search import list_fields, list_periods, overview, search_facts
from ashare_f10.calculate.formula import FormulaError, evaluate_formula
from ashare_f10.calculate.ttm import compute_ttm
from ashare_f10.config import settings
from ashare_f10.models import FormulaRequest, TTMRequest


class CreateJobRequest(BaseModel):
    stock_code: str
    resume: bool = True


app = FastAPI(
    title="A股F10投研平台",
    version="0.1.0",
    description="A-share F10 collection, search, TTM and formula research platform",
)
manager = JobManager(settings)


def latest_paths(stock_code: str) -> tuple[dict[str, Any], Path]:
    pointer = manager.latest(stock_code)
    if not pointer:
        raise HTTPException(status_code=404, detail="尚未找到该股票的已完成任务")
    output_dir = Path(pointer["output_dir"])
    db_path = Path(pointer["artifacts"].get("duckdb", output_dir / "normalized/f10.duckdb"))
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="DuckDB数据文件不存在")
    return pointer, db_path


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
def list_jobs(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    return [state.model_dump() for state in manager.list(limit)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    state = manager.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state.model_dump()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="任务不存在或已结束")
    return {"job_id": job_id, "cancel_requested": True}


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
    _, db_path = latest_paths(stock_code)
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
