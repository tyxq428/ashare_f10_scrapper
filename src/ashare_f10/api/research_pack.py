from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ashare_f10.config import settings
from ashare_f10.cross_validation.runner import run_full_cross_validation
from ashare_f10.research_pack.runner import run_research_pack

router = APIRouter(prefix="/api/research-pack", tags=["research-pack"])
_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}

ResearchMode = Literal["thin-slice", "research-full"]
MODE_MAX_PERIODS: dict[str, int | None] = {
    "thin-slice": 2,
    "research-full": None,
}
DOWNLOAD_NAMES = {
    "json": "package_json",
    "excel": "package_excel",
    "duckdb": "package_duckdb",
    "summary": "summary_json",
    "quality": "quality_json",
    "manifest": "manifest_json",
    "checkpoint": "checkpoint_json",
}
SORT_COLUMNS = {
    "metric_id",
    "metric_name_cn",
    "research_module",
    "report_date",
    "event_date",
    "period_type",
    "status",
    "confidence",
    "source_count",
    "conflict_count",
}


class ResearchPackJobRequest(BaseModel):
    stock_code: str
    mode: ResearchMode = "thin-slice"
    as_of_date: str | None = None
    force: bool = False


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _latest_f10_output(stock_code: str) -> Path:
    pointer_path = settings.data_dir / stock_code / "latest.json"
    if not pointer_path.exists():
        raise FileNotFoundError("尚无该股票的完整F10版本，请先运行F10任务")
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    output_dir = Path(str(payload["output_dir"]))
    if not output_dir.exists():
        raise FileNotFoundError("F10最新版本目录不存在")
    return output_dir


def _fallback_pointer(run_dir: Path) -> dict[str, Any] | None:
    artifacts_path = run_dir / "artifacts.json"
    if not artifacts_path.exists():
        return None
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    output_value = artifacts.get("research_pack")
    if not output_value:
        return None
    output_dir = Path(str(output_value))
    if not output_dir.is_absolute():
        output_dir = run_dir / output_dir
    if not output_dir.exists():
        return None
    stock_code = run_dir.parent.name
    return {
        "stock_code": stock_code,
        "mode": "unknown",
        "as_of_date": None,
        "run_dir": str(run_dir),
        "output_dir": str(output_dir),
        "artifacts": {
            "output_dir": str(output_dir),
            "manifest_json": str(output_dir / "manifest.json"),
            "summary_json": str(output_dir / "summary.json"),
            "package_json": str(output_dir / "exports" / f"{stock_code}_research_pack.json"),
            "package_excel": str(output_dir / "exports" / f"{stock_code}_research_pack.xlsx"),
            "package_duckdb": str(output_dir / "exports" / f"{stock_code}_research_pack.duckdb"),
            "quality_json": str(output_dir / "quality" / "research_pack_quality.json"),
            "checkpoint_json": str(output_dir / "checkpoint.json"),
        },
    }


def _latest_pointer(stock_code: str) -> dict[str, Any]:
    run_dir = _latest_f10_output(stock_code)
    pointer_path = run_dir / "research_pack" / "latest.json"
    if pointer_path.exists():
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    else:
        pointer = _fallback_pointer(run_dir)
        if pointer is None:
            raise FileNotFoundError("尚无该股票的Research Pack，请先生成")
    pointer["run_dir"] = str(run_dir)
    return pointer


def _read_json(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(pointer: dict[str, Any], name: str) -> Path:
    value = (pointer.get("artifacts") or {}).get(name)
    if not value:
        raise FileNotFoundError(f"Research Pack缺少Artifact：{name}")
    path = Path(str(value))
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Research Pack Artifact不存在：{path}")
    return path


def _database(stock_code: str) -> tuple[dict[str, Any], Path]:
    pointer = _latest_pointer(stock_code)
    return pointer, _artifact(pointer, "package_duckdb")


def _set_job(job_id: str, **updates: Any) -> None:
    with _LOCK:
        state = _JOBS[job_id]
        state.update(updates, updated_at_utc=utc_now())


def _run_job(job_id: str, request: ResearchPackJobRequest) -> None:
    try:
        _set_job(job_id, status="RUNNING", stage="RESOLVE_INPUT", message="正在定位最新F10版本")
        run_dir = _latest_f10_output(request.stock_code)
        mode_slug = request.mode.replace("-", "_")
        cross_dir = run_dir / "cross_validation" / mode_slug
        research_dir = run_dir / "research_pack" / mode_slug

        _set_job(job_id, stage="CROSS_VALIDATION", message="正在生成免费官方双源验证数据")
        cross_summary = run_full_cross_validation(
            request.stock_code,
            run_dir,
            cross_dir,
            max_periods=MODE_MAX_PERIODS[request.mode],
            as_of_date=request.as_of_date,
        )

        _set_job(job_id, stage="RESEARCH_PACK", message="正在生成规范事实和证据图")
        result = run_research_pack(
            request.stock_code,
            run_dir,
            research_dir,
            as_of_date=request.as_of_date,
            force=request.force,
        )
        artifacts = result["artifacts"]
        pointer = {
            "stock_code": request.stock_code,
            "mode": request.mode,
            "as_of_date": result.get("summary", {}).get("as_of_date"),
            "run_dir": str(run_dir),
            "output_dir": artifacts["output_dir"],
            "cross_validation_summary": str(cross_dir / "cross_validation_summary.json"),
            "cross_validation_acceptance_status": cross_summary.get("acceptance_status"),
            "manual_review_required": bool(cross_summary.get("manual_review_required")),
            "artifacts": artifacts,
            "completed_at_utc": utc_now(),
        }
        _write_json(run_dir / "research_pack" / "latest.json", pointer)
        _set_job(
            job_id,
            status="COMPLETED",
            stage="COMPLETED",
            message="Research Pack完成",
            result=result,
            pointer=pointer,
            manual_review_required=pointer["manual_review_required"],
        )
    except Exception as exc:  # noqa: BLE001
        _set_job(
            job_id,
            status="FAILED",
            stage="FAILED",
            message=str(exc),
            error=f"{type(exc).__name__}: {exc}",
        )


def _job_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (FileNotFoundError, LookupError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _quality_dimensions(pointer: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    cross = _read_json(pointer.get("cross_validation_summary"))
    mapping = summary.get("mapping_coverage") or {}
    evidence = summary.get("evidence_quality") or {}
    return {
        "classification_coverage": cross.get("classification_coverage"),
        "comparison_coverage": cross.get("comparison_coverage"),
        "comparison_accuracy": cross.get("comparison_accuracy"),
        "evidence_completeness": cross.get(
            "evidence_completeness", evidence.get("observation_evidence_coverage")
        ),
        "mapping_coverage": mapping.get("mapping_coverage"),
        "suspicious_extraction_rate": cross.get("suspicious_extraction_rate"),
        "unresolved_rate": cross.get("unresolved_rate"),
        "true_conflict_count": cross.get("true_conflict_count", 0),
        "source_conflict_count": mapping.get("source_conflict_count", 0),
        "acceptance_status": cross.get("acceptance_status"),
    }


def _records(connection: duckdb.DuckDBPyConnection, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    frame = connection.execute(sql, params).fetch_df()
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _parse_node_attributes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        raw = row.get("attributes_json")
        if isinstance(raw, str):
            try:
                row["attributes"] = json.loads(raw)
            except json.JSONDecodeError:
                row["attributes"] = {"raw": raw}
    return rows


@router.get("/capabilities")
def research_pack_capabilities() -> dict[str, Any]:
    return {
        "modes": [
            {
                "id": "thin-slice",
                "label": "最近两期薄切片",
                "description": "验证最近两个报告期后生成Research Pack，适合快速检查。",
                "max_periods": 2,
            },
            {
                "id": "research-full",
                "label": "全历史研究包",
                "description": "验证全部可用报告期并生成完整Research Pack。",
                "max_periods": None,
            },
        ],
        "issue_filters": ["parse_suspect", "source_conflict", "unresolved"],
        "quality_dimensions": [
            "classification_coverage",
            "comparison_coverage",
            "comparison_accuracy",
            "evidence_completeness",
        ],
        "downloads": sorted(DOWNLOAD_NAMES),
    }


@router.post("/jobs")
def create_research_pack_job(request: ResearchPackJobRequest) -> dict[str, Any]:
    try:
        _latest_f10_output(request.stock_code)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    job_id = f"research-{request.stock_code}-{uuid.uuid4().hex[:10]}"
    state = {
        "job_id": job_id,
        "stock_code": request.stock_code,
        "mode": request.mode,
        "as_of_date": request.as_of_date,
        "force": request.force,
        "status": "PENDING",
        "stage": "PENDING",
        "message": "任务已创建",
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
    }
    with _LOCK:
        _JOBS[job_id] = state
    threading.Thread(target=_run_job, args=(job_id, request), daemon=True).start()
    return state


@router.get("/jobs")
def list_research_pack_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        return list(reversed(list(_JOBS.values())))


@router.get("/jobs/{job_id}")
def get_research_pack_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _JOBS.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Research Pack任务不存在")
    return state


@router.get("/stocks/{stock_code}/latest")
def get_latest_research_pack(stock_code: str) -> dict[str, Any]:
    try:
        pointer = _latest_pointer(stock_code)
        summary = _read_json((pointer.get("artifacts") or {}).get("summary_json"))
        quality = _read_json((pointer.get("artifacts") or {}).get("quality_json"))
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return {
        "pointer": pointer,
        "summary": summary,
        "quality": quality,
        "quality_dimensions": _quality_dimensions(pointer, summary),
    }


@router.get("/stocks/{stock_code}/facts")
def query_research_facts(
    stock_code: str,
    q: str = "",
    research_module: str | None = None,
    status: str | None = None,
    source_status: str | None = None,
    issue: Literal["parse_suspect", "source_conflict", "unresolved"] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sort_by: str = "report_date",
    sort_direction: Literal["asc", "desc"] = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        _, database = _database(stock_code)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc

    filters: list[str] = []
    params: list[Any] = []
    if q.strip():
        needle = f"%{q.strip().lower()}%"
        filters.append(
            "(lower(c.metric_id) LIKE ? OR lower(c.metric_name_cn) LIKE ? "
            "OR lower(coalesce(c.value_text, '')) LIKE ?)"
        )
        params.extend([needle, needle, needle])
    if research_module:
        filters.append("c.research_module = ?")
        params.append(research_module)
    if status:
        filters.append("c.status = ?")
        params.append(status)
    if start_date:
        filters.append("coalesce(c.report_date, c.event_date) >= ?")
        params.append(start_date)
    if end_date:
        filters.append("coalesce(c.report_date, c.event_date) <= ?")
        params.append(end_date)

    source_exists = (
        "EXISTS (SELECT 1 FROM fact_lineage l JOIN source_facts s "
        "ON s.source_fact_id = l.source_fact_id "
        "WHERE l.observation_id = c.observation_id"
    )
    if source_status:
        filters.append(source_exists + " AND s.source_status = ?)")
        params.append(source_status)
    if issue == "parse_suspect":
        filters.append(source_exists + " AND (s.source_status = 'PARSE_SUSPECT' OR s.is_quarantined))")
    elif issue == "source_conflict":
        filters.append("c.status = 'SOURCE_CONFLICT'")
    elif issue == "unresolved":
        filters.append("(c.status = 'UNRESOLVED' OR c.usable_source_count = 0)")

    where = " WHERE " + " AND ".join(filters) if filters else ""
    order_column = sort_by if sort_by in SORT_COLUMNS else "report_date"
    direction = "ASC" if sort_direction == "asc" else "DESC"
    base_sql = f"FROM canonical_observations c{where}"

    connection = duckdb.connect(str(database), read_only=True)
    try:
        total = int(connection.execute(f"SELECT count(*) {base_sql}", params).fetchone()[0])
        rows = _records(
            connection,
            f"SELECT c.* {base_sql} ORDER BY c.{order_column} {direction} NULLS LAST "
            "LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        modules = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT research_module FROM canonical_observations "
                "WHERE research_module IS NOT NULL ORDER BY research_module"
            ).fetchall()
        ]
    finally:
        connection.close()
    return {"rows": rows, "total": total, "offset": offset, "limit": limit, "modules": modules}


@router.get("/stocks/{stock_code}/facts/{observation_id}/evidence")
def get_fact_evidence(stock_code: str, observation_id: str) -> dict[str, Any]:
    try:
        _, database = _database(stock_code)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    connection = duckdb.connect(str(database), read_only=True)
    try:
        observation = _records(
            connection,
            "SELECT * FROM canonical_observations WHERE observation_id = ?",
            [observation_id],
        )
        if not observation:
            raise HTTPException(status_code=404, detail="规范事实不存在")
        lineage = _records(
            connection,
            "SELECT l.*, s.* EXCLUDE (source_fact_id) FROM fact_lineage l "
            "LEFT JOIN source_facts s ON s.source_fact_id = l.source_fact_id "
            "WHERE l.observation_id = ? ORDER BY l.source_priority DESC, l.role",
            [observation_id],
        )
        nodes = _records(
            connection,
            """
            WITH RECURSIVE reach(node_id, depth) AS (
                SELECT CAST(? AS VARCHAR), 0
                UNION
                SELECT edge.to_node_id, reach.depth + 1
                FROM reach
                JOIN evidence_edges edge ON edge.from_node_id = reach.node_id
                WHERE reach.depth < 4
            )
            SELECT node.* FROM evidence_nodes node
            JOIN reach ON reach.node_id = node.node_id
            ORDER BY reach.depth, node.node_type, node.node_id
            """,
            [observation_id],
        )
        edges = _records(
            connection,
            """
            WITH RECURSIVE reach(node_id, depth) AS (
                SELECT CAST(? AS VARCHAR), 0
                UNION
                SELECT edge.to_node_id, reach.depth + 1
                FROM reach
                JOIN evidence_edges edge ON edge.from_node_id = reach.node_id
                WHERE reach.depth < 4
            )
            SELECT DISTINCT edge.* FROM evidence_edges edge
            JOIN reach source_reach ON source_reach.node_id = edge.from_node_id
            JOIN reach target_reach ON target_reach.node_id = edge.to_node_id
            ORDER BY edge.edge_type, edge.from_node_id, edge.to_node_id
            """,
            [observation_id],
        )
    finally:
        connection.close()
    return {
        "observation": observation[0],
        "lineage": lineage,
        "nodes": _parse_node_attributes(nodes),
        "edges": edges,
    }


@router.get("/stocks/{stock_code}/versions")
def get_document_versions(stock_code: str) -> dict[str, Any]:
    try:
        pointer, database = _database(stock_code)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    connection = duckdb.connect(str(database), read_only=True)
    try:
        documents = _records(
            connection,
            "SELECT * FROM evidence_nodes WHERE node_type = 'DOCUMENT' "
            "AND security_code = ? ORDER BY node_id",
            [stock_code],
        )
        edges = _records(
            connection,
            "SELECT * FROM evidence_edges WHERE edge_type = 'SUPERSEDES' ORDER BY from_node_id",
            [],
        )
    finally:
        connection.close()
    parsed = _parse_node_attributes(documents)
    parsed.sort(
        key=lambda item: (
            str((item.get("attributes") or {}).get("report_date") or ""),
            str((item.get("attributes") or {}).get("available_at") or ""),
        ),
        reverse=True,
    )
    return {
        "stock_code": stock_code,
        "as_of_date": pointer.get("as_of_date"),
        "mode": pointer.get("mode"),
        "documents": parsed,
        "supersedes_edges": edges,
    }


@router.get("/stocks/{stock_code}/coverage-gaps")
def get_coverage_gaps(
    stock_code: str,
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        _, database = _database(stock_code)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    connection = duckdb.connect(str(database), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        if "coverage_gaps" not in tables:
            return {"rows": [], "total": 0, "offset": offset, "limit": limit}
        params: list[Any] = []
        where = ""
        if q.strip():
            columns = [
                row[1] for row in connection.execute("PRAGMA table_info('coverage_gaps')").fetchall()
            ]
            searchable = []
            for column in columns:
                escaped = str(column).replace('"', '""')
                searchable.append(f'lower(CAST("{escaped}" AS VARCHAR)) LIKE ?')
            if searchable:
                where = " WHERE " + " OR ".join(searchable)
                params.extend([f"%{q.strip().lower()}%"] * len(searchable))
        total = int(
            connection.execute(f"SELECT count(*) FROM coverage_gaps{where}", params).fetchone()[0]
        )
        rows = _records(
            connection,
            f"SELECT * FROM coverage_gaps{where} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
    finally:
        connection.close()
    return {"rows": rows, "total": total, "offset": offset, "limit": limit}


@router.get("/stocks/{stock_code}/download/{kind}")
def download_research_pack(stock_code: str, kind: str) -> FileResponse:
    artifact_name = DOWNLOAD_NAMES.get(kind)
    if artifact_name is None:
        raise HTTPException(status_code=404, detail="未知Research Pack Artifact类型")
    try:
        pointer = _latest_pointer(stock_code)
        path = _artifact(pointer, artifact_name)
    except Exception as exc:  # noqa: BLE001
        raise _job_error(exc) from exc
    return FileResponse(path, filename=path.name)


__all__ = [
    "ResearchPackJobRequest",
    "get_latest_research_pack",
    "query_research_facts",
    "research_pack_capabilities",
    "router",
]
