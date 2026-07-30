from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.ascope_bridge.finance import (
    FinanceExportResult,
    IndustryTemplate,
    build_financial_tables,
)

EXPORT_SCHEMA_VERSION = "1.0.0"
MAPPING_VERSION = "ascope-finance-v1"
REQUIRED_EXPORTS = (
    "financial_annual.csv",
    "financial_quarterly.csv",
    "financial_field_status.csv",
    "data_gaps.csv",
    "future_available_rows.csv",
    "duplicate_resolution.csv",
    "single_stock_manifest.json",
)


class SingleStockExportError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class SourceRun:
    stock_code: str
    job_id: str
    run_dir: Path
    facts_path: Path
    pointer_path: Path | None
    pointer_updated_at_utc: str
    source_status: str


@dataclass(frozen=True, slots=True)
class SingleStockExportResult:
    status: str
    cache_status: str
    security_id: str
    stock_code: str
    output_dir: str
    manifest_path: str
    annual_rows: int
    quarterly_rows: int
    field_status_rows: int
    data_gap_rows: int
    fingerprint: str
    source_job_id: str
    source_run_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request_dict(request: Mapping[str, Any] | Any) -> dict[str, Any]:
    if is_dataclass(request):
        raw = asdict(request)
    elif isinstance(request, Mapping):
        raw = dict(request)
    else:
        raw = {
            key: getattr(request, key)
            for key in (
                "batch_id",
                "security_id",
                "code",
                "name",
                "exchange",
                "request_annual_from",
                "request_quarterly_from",
                "request_through",
                "required_available_at",
                "request_status",
            )
            if hasattr(request, key)
        }
    required = {
        "security_id",
        "code",
        "name",
        "request_annual_from",
        "request_quarterly_from",
        "request_through",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise SingleStockExportError("REQUEST_ROW_INVALID", f"missing fields: {missing}")
    raw["security_id"] = str(raw["security_id"])
    raw["code"] = str(raw["code"]).zfill(6)
    raw["name"] = str(raw["name"])
    return raw


def infer_industry_template(name: str) -> IndustryTemplate:
    text = str(name or "").strip()
    if "银行" in text:
        return IndustryTemplate.BANK
    if "保险" in text:
        return IndustryTemplate.INSURANCE
    if any(token in text for token in ("证券", "券商")):
        return IndustryTemplate.SECURITIES
    if any(token in text for token in ("信托", "金控", "金融租赁", "消费金融")):
        return IndustryTemplate.OTHER_FINANCIAL
    return IndustryTemplate.INDUSTRIAL


def _resolve_run_dir(value: str, *, data_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = [data_root / path, data_root.parent / path, Path.cwd() / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (data_root / path).resolve()


def _find_facts(run_dir: Path) -> Path:
    candidates = (
        run_dir / "normalized" / "facts.parquet",
        run_dir / "normalized" / "f10.duckdb",
        run_dir / "normalized" / "facts.csv",
        run_dir / "facts.parquet",
        run_dir / "facts.csv",
    )
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    raise SingleStockExportError("SOURCE_FACTS_NOT_FOUND", str(run_dir))


def locate_current_run(data_root: Path | str, stock_code: str) -> SourceRun:
    root = Path(data_root)
    code = str(stock_code).zfill(6)
    pointer = root / code / "latest.json"
    if not pointer.exists():
        raise SingleStockExportError("CURRENT_RUN_NOT_FOUND", str(pointer))
    try:
        value = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SingleStockExportError("CURRENT_RUN_POINTER_INVALID", str(pointer)) from exc
    pointer_code = str(value.get("stock_code") or "").zfill(6)
    if pointer_code != code:
        raise SingleStockExportError(
            "CURRENT_RUN_SECURITY_MISMATCH", f"pointer={pointer_code}, request={code}"
        )
    status = str(value.get("status") or "").upper()
    failed_groups = int(value.get("failed_groups") or 0)
    if status != "COMPLETED" or failed_groups != 0:
        raise SingleStockExportError(
            "CURRENT_RUN_INCOMPLETE", f"status={status}, failed_groups={failed_groups}"
        )
    run_dir = _resolve_run_dir(str(value.get("output_dir") or ""), data_root=root)
    if not run_dir.exists():
        raise SingleStockExportError("CURRENT_RUN_DIRECTORY_NOT_FOUND", str(run_dir))
    facts_path = _find_facts(run_dir)
    return SourceRun(
        stock_code=code,
        job_id=str(value.get("job_id") or run_dir.name),
        run_dir=run_dir,
        facts_path=facts_path,
        pointer_path=pointer,
        pointer_updated_at_utc=str(value.get("updated_at_utc") or ""),
        source_status=status,
    )


def source_run_from_directory(run_dir: Path | str, stock_code: str) -> SourceRun:
    path = Path(run_dir).resolve()
    if not path.exists():
        raise SingleStockExportError("SOURCE_RUN_DIRECTORY_NOT_FOUND", str(path))
    combined = path / "combined.json"
    artifacts = path / "artifacts.json"
    if not combined.exists() or not artifacts.exists():
        raise SingleStockExportError(
            "SOURCE_RUN_INCOMPLETE", f"missing combined.json or artifacts.json in {path}"
        )
    try:
        payload = json.loads(combined.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SingleStockExportError("SOURCE_RUN_COMBINED_INVALID", str(combined)) from exc
    failed = int(payload.get("metadata", {}).get("failed_group_count", 0))
    if failed:
        raise SingleStockExportError("SOURCE_RUN_INCOMPLETE", f"failed_group_count={failed}")
    facts_path = _find_facts(path)
    return SourceRun(
        stock_code=str(stock_code).zfill(6),
        job_id=path.name,
        run_dir=path,
        facts_path=facts_path,
        pointer_path=None,
        pointer_updated_at_utc="",
        source_status="COMPLETED",
    )


def read_source_facts(source: SourceRun) -> pd.DataFrame:
    path = source.facts_path
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype={"security_code": str})
    if path.suffix.lower() == ".duckdb":
        try:
            import duckdb
        except ImportError as exc:  # pragma: no cover - project dependency in production
            raise SingleStockExportError("DUCKDB_DEPENDENCY_MISSING", str(path)) from exc
        connection = duckdb.connect(str(path), read_only=True)
        try:
            return connection.execute("select * from facts").fetchdf()
        finally:
            connection.close()
    raise SingleStockExportError("SOURCE_FACTS_FORMAT_UNSUPPORTED", str(path))


def _write_frame(frame: pd.DataFrame, path: Path, columns: tuple[str, ...] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = frame.copy()
    if value.empty and columns:
        value = pd.DataFrame(columns=list(columns))
    value.to_csv(path, index=False, encoding="utf-8-sig")


def _filter_period(frame: pd.DataFrame, start: str, through: str) -> pd.DataFrame:
    if frame.empty or "report_period" not in frame:
        return frame.copy()
    periods = frame["report_period"].astype(str).str[:10]
    return frame[(periods >= start) & (periods <= through)].copy()


def _validate_formal_output(frame: pd.DataFrame, *, as_of_date: str, label: str) -> None:
    if frame.empty:
        return
    required = {"security_id", "report_period", "available_at"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SingleStockExportError("EXPORT_SCHEMA_INVALID", f"{label} missing {missing}")
    if frame[["security_id", "report_period"]].duplicated().any():
        raise SingleStockExportError("EXPORT_DUPLICATE_KEY", label)
    availability = frame["available_at"].fillna("").astype(str).str[:10]
    if (availability == "").any():
        raise SingleStockExportError("EXPORT_AVAILABLE_AT_MISSING", label)
    if (availability > as_of_date).any():
        raise SingleStockExportError("EXPORT_FUTURE_ROW", label)


def _required_files_exist(output_dir: Path) -> bool:
    return all((output_dir / name).exists() for name in REQUIRED_EXPORTS)


def export_single_stock(
    request: Mapping[str, Any] | Any,
    *,
    data_root: Path | str,
    output_root: Path | str,
    as_of_date: str,
    industry_template: IndustryTemplate | str | None = None,
    source_run_dir: Path | str | None = None,
    disclosure_dates: pd.DataFrame | None = None,
    force: bool = False,
    mapper: Callable[..., FinanceExportResult] = build_financial_tables,
) -> SingleStockExportResult:
    row = _request_dict(request)
    code = row["code"]
    if str(as_of_date) != str(row["request_through"]):
        raise SingleStockExportError(
            "REQUEST_CUTOFF_MISMATCH",
            f"request={row['request_through']}, export={as_of_date}",
        )
    source = (
        source_run_from_directory(source_run_dir, code)
        if source_run_dir is not None
        else locate_current_run(data_root, code)
    )
    template = (
        industry_template
        if isinstance(industry_template, IndustryTemplate)
        else IndustryTemplate(str(industry_template))
        if industry_template
        else infer_industry_template(row["name"])
    )
    source_facts_sha = _file_sha256(source.facts_path)
    decision = {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "mapping_version": MAPPING_VERSION,
        "request": row,
        "as_of_date": str(as_of_date),
        "industry_template": template.value,
        "source_facts_sha256": source_facts_sha,
        "source_job_id": source.job_id,
        "source_run_dir": str(source.run_dir),
    }
    fingerprint = _json_sha256(decision)
    output_dir = Path(output_root) / row["security_id"]
    manifest_path = output_dir / "single_stock_manifest.json"
    if not force and manifest_path.exists() and _required_files_exist(output_dir):
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if existing.get("fingerprint") == fingerprint and existing.get("status") in {
            "PASS",
            "PASS_WITH_GAPS",
        }:
            return SingleStockExportResult(
                status=str(existing["status"]),
                cache_status="CACHE_HIT",
                security_id=row["security_id"],
                stock_code=code,
                output_dir=str(output_dir),
                manifest_path=str(manifest_path),
                annual_rows=int(existing.get("annual_rows", 0)),
                quarterly_rows=int(existing.get("quarterly_rows", 0)),
                field_status_rows=int(existing.get("field_status_rows", 0)),
                data_gap_rows=int(existing.get("data_gap_rows", 0)),
                fingerprint=fingerprint,
                source_job_id=source.job_id,
                source_run_dir=str(source.run_dir),
            )
    facts = read_source_facts(source)
    if "security_code" in facts:
        facts["security_code"] = facts["security_code"].astype(str).str.zfill(6)
        facts = facts[facts["security_code"] == code].copy()
    if facts.empty:
        raise SingleStockExportError("SOURCE_FACTS_EMPTY", code)
    mapped = mapper(
        facts,
        security_id=row["security_id"],
        security_code=code,
        industry_template=template,
        as_of_date=str(as_of_date),
        disclosure_dates=disclosure_dates,
    )
    annual = _filter_period(
        mapped.annual, str(row["request_annual_from"]), str(row["request_through"])
    )
    quarterly = _filter_period(
        mapped.quarterly,
        str(row["request_quarterly_from"]),
        str(row["request_through"]),
    )
    status_frame = mapped.field_status.copy()
    if not status_frame.empty and "report_period" in status_frame:
        status_frame = status_frame[
            status_frame["report_period"].astype(str).str[:10] <= str(row["request_through"])
        ].copy()
    _validate_formal_output(annual, as_of_date=str(as_of_date), label="annual")
    _validate_formal_output(quarterly, as_of_date=str(as_of_date), label="quarterly")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_frame(
        annual,
        output_dir / "financial_annual.csv",
        ("security_id", "report_period", "available_at", "industry_template"),
    )
    _write_frame(
        quarterly,
        output_dir / "financial_quarterly.csv",
        ("security_id", "report_period", "available_at", "industry_template"),
    )
    _write_frame(status_frame, output_dir / "financial_field_status.csv")
    _write_frame(mapped.data_gaps, output_dir / "data_gaps.csv")
    _write_frame(mapped.future_rows, output_dir / "future_available_rows.csv")
    _write_frame(mapped.duplicate_resolution, output_dir / "duplicate_resolution.csv")
    data_gap_rows = len(mapped.data_gaps)
    status = "PASS_WITH_GAPS" if data_gap_rows else "PASS"
    manifest = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "mapping_version": MAPPING_VERSION,
        "status": status,
        "cache_status": "CACHE_MISS",
        "security_id": row["security_id"],
        "stock_code": code,
        "stock_name": row["name"],
        "industry_template": template.value,
        "as_of_date": str(as_of_date),
        "fingerprint": fingerprint,
        "request_sha256": _json_sha256(row),
        "source_facts_sha256": source_facts_sha,
        "source_job_id": source.job_id,
        "source_run_dir": str(source.run_dir),
        "source_pointer": str(source.pointer_path or ""),
        "source_pointer_updated_at_utc": source.pointer_updated_at_utc,
        "annual_rows": len(annual),
        "quarterly_rows": len(quarterly),
        "field_status_rows": len(status_frame),
        "data_gap_rows": data_gap_rows,
        "future_rows": len(mapped.future_rows),
        "duplicate_resolution_rows": len(mapped.duplicate_resolution),
        "decision_input": decision,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return SingleStockExportResult(
        status=status,
        cache_status="CACHE_MISS",
        security_id=row["security_id"],
        stock_code=code,
        output_dir=str(output_dir),
        manifest_path=str(manifest_path),
        annual_rows=len(annual),
        quarterly_rows=len(quarterly),
        field_status_rows=len(status_frame),
        data_gap_rows=data_gap_rows,
        fingerprint=fingerprint,
        source_job_id=source.job_id,
        source_run_dir=str(source.run_dir),
    )
