from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd

SUCCESS_STATUSES = {"COMPLETED", "COMPLETED_WITH_GAPS"}
FAILED_STATUSES = {"FAILED_RETRYABLE", "FAILED_TERMINAL", "BLOCKED"}
DEFERRED_STATUSES = {"DEFERRED_TIME_BUDGET"}

ANNUAL_COLUMNS = (
    "security_id",
    "report_period",
    "available_at",
    "industry_template",
)
QUARTERLY_COLUMNS = (
    "security_id",
    "report_period",
    "available_at",
    "industry_template",
    "quarter",
)
STATUS_COLUMNS = (
    "security_id",
    "security_code",
    "report_period",
    "field_name",
    "status",
)
LEDGER_COLUMNS = (
    "security_id",
    "stock_code",
    "stock_name",
    "status",
    "attempt_count",
    "error_code",
    "message",
    "updated_at_utc",
)


class BatchReductionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class BatchReductionResult:
    status: str
    batch_id: str
    output_dir: str
    input_count: int
    successful_count: int
    failed_count: int
    deferred_count: int
    annual_rows: int
    quarterly_rows: int
    field_status_rows: int
    data_gap_rows: int
    validation_report_path: str
    batch_manifest_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _row_dict(row: Any) -> dict[str, Any]:
    if is_dataclass(row):
        return asdict(row)
    if isinstance(row, Mapping):
        return dict(row)
    return {
        name: getattr(row, name)
        for name in (
            "security_id",
            "code",
            "name",
            "request_annual_from",
            "request_quarterly_from",
            "request_through",
        )
        if hasattr(row, name)
    }


def _read_csv(path: Path, *, columns: tuple[str, ...] = ()) -> pd.DataFrame:
    if not path.exists():
        raise BatchReductionError("REDUCTION_STOCK_OUTPUT_MISSING", str(path))
    if path.stat().st_size == 0:
        return pd.DataFrame(columns=list(columns))
    try:
        frame = pd.read_csv(
            path,
            dtype={"security_id": str, "stock_code": str},
        )
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame(columns=list(columns))
    return frame


def _concat(
    frames: list[pd.DataFrame], *, columns: tuple[str, ...] = ()
) -> pd.DataFrame:
    usable = [frame for frame in frames if frame is not None and not frame.empty]
    if not usable:
        return pd.DataFrame(columns=list(columns))
    return pd.concat(usable, ignore_index=True, sort=False)


def _write_csv(
    frame: pd.DataFrame, path: Path, *, columns: tuple[str, ...] = ()
) -> None:
    value = frame.copy()
    if value.empty and columns:
        value = pd.DataFrame(columns=list(columns))
    value.to_csv(path, index=False, encoding="utf-8-sig")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_formal(
    frame: pd.DataFrame,
    *,
    label: str,
    cutoff: str,
    successful_ids: set[str],
    request_by_id: dict[str, dict[str, Any]],
) -> None:
    if frame.empty:
        return
    required = {"security_id", "report_period", "available_at"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise BatchReductionError(
            "REDUCTION_SCHEMA_INVALID", f"{label} missing columns {missing}"
        )
    frame["security_id"] = frame["security_id"].astype(str)
    unknown = sorted(set(frame["security_id"]) - successful_ids)
    if unknown:
        raise BatchReductionError(
            "REDUCTION_UNKNOWN_SECURITY", f"{label}: {unknown[:20]}"
        )
    if frame[["security_id", "report_period"]].duplicated().any():
        raise BatchReductionError("REDUCTION_DUPLICATE_KEY", label)
    available = frame["available_at"].fillna("").astype(str).str[:10]
    if (available == "").any():
        raise BatchReductionError("REDUCTION_AVAILABLE_AT_MISSING", label)
    if (available > cutoff).any():
        raise BatchReductionError("REDUCTION_FUTURE_ROW", label)
    for security_id, group in frame.groupby("security_id"):
        request = request_by_id[security_id]
        start_key = (
            "request_annual_from"
            if label == "annual"
            else "request_quarterly_from"
        )
        periods = group["report_period"].astype(str).str[:10]
        if (periods < str(request[start_key])).any() or (
            periods > str(request["request_through"])
        ).any():
            raise BatchReductionError(
                "REDUCTION_PERIOD_OUT_OF_RANGE", f"{label}:{security_id}"
            )


def _ledger(stocks: list[dict[str, Any]], statuses: set[str]) -> pd.DataFrame:
    rows = [
        {key: item.get(key) for key in LEDGER_COLUMNS}
        for item in stocks
        if str(item.get("status")) in statuses
    ]
    return pd.DataFrame(rows, columns=list(LEDGER_COLUMNS))


def _coverage(
    field_status: pd.DataFrame, templates: dict[str, str]
) -> pd.DataFrame:
    if field_status.empty:
        return pd.DataFrame(
            columns=["industry_template", "field_name", "status", "row_count"]
        )
    value = field_status.copy()
    value["industry_template"] = (
        value["security_id"].astype(str).map(templates).fillna("")
    )
    return (
        value.groupby(
            ["industry_template", "field_name", "status"],
            dropna=False,
        )
        .size()
        .reset_index(name="row_count")
        .sort_values(["industry_template", "field_name", "status"])
        .reset_index(drop=True)
    )


def reduce_batch(
    resolved: Any, *, batch_output_dir: Path | str
) -> BatchReductionResult:
    output = Path(batch_output_dir)
    checkpoint_path = output / "checkpoint.json"
    if not checkpoint_path.exists():
        raise BatchReductionError(
            "REDUCTION_CHECKPOINT_MISSING", str(checkpoint_path)
        )
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchReductionError(
            "REDUCTION_CHECKPOINT_INVALID", str(checkpoint_path)
        ) from exc
    batch_id = str(getattr(resolved, "batch_id", "") or "")
    rows = [_row_dict(row) for row in getattr(resolved, "rows", ())]
    manifest = getattr(resolved, "manifest", None)
    cutoff = str(
        getattr(manifest, "through", "")
        or (rows[0]["request_through"] if rows else "")
    )
    if checkpoint.get("batch_id") != batch_id:
        raise BatchReductionError("REDUCTION_BATCH_MISMATCH", batch_id)
    requested_ids = [str(row["security_id"]) for row in rows]
    stocks = list(checkpoint.get("stocks", []))
    checkpoint_ids = [str(item.get("security_id") or "") for item in stocks]
    if checkpoint_ids != requested_ids:
        raise BatchReductionError(
            "REDUCTION_REQUEST_MISMATCH", "checkpoint securities differ"
        )
    if len(set(checkpoint_ids)) != len(checkpoint_ids):
        raise BatchReductionError(
            "REDUCTION_DUPLICATE_SECURITY", "checkpoint"
        )
    request_by_id = {str(row["security_id"]): row for row in rows}
    successful = [
        item for item in stocks if item.get("status") in SUCCESS_STATUSES
    ]
    failed = [item for item in stocks if item.get("status") in FAILED_STATUSES]
    deferred = [
        item for item in stocks if item.get("status") in DEFERRED_STATUSES
    ]
    unresolved = [
        item
        for item in stocks
        if item.get("status")
        not in SUCCESS_STATUSES | FAILED_STATUSES | DEFERRED_STATUSES
    ]
    if unresolved:
        raise BatchReductionError(
            "REDUCTION_NONTERMINAL_STATUS",
            ",".join(str(item.get("security_id")) for item in unresolved[:20]),
        )
    annual_frames: list[pd.DataFrame] = []
    quarterly_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []
    gap_frames: list[pd.DataFrame] = []
    future_frames: list[pd.DataFrame] = []
    duplicate_frames: list[pd.DataFrame] = []
    templates: dict[str, str] = {}
    stock_manifests: list[dict[str, Any]] = []
    for item in successful:
        security_id = str(item["security_id"])
        stock_dir = output / "stocks" / security_id
        manifest_path = stock_dir / "single_stock_manifest.json"
        if not manifest_path.exists():
            raise BatchReductionError(
                "REDUCTION_STOCK_OUTPUT_MISSING", str(manifest_path)
            )
        try:
            stock_manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BatchReductionError(
                "REDUCTION_STOCK_MANIFEST_INVALID", str(manifest_path)
            ) from exc
        if stock_manifest.get("security_id") != security_id:
            raise BatchReductionError(
                "REDUCTION_STOCK_ID_MISMATCH", security_id
            )
        if stock_manifest.get("as_of_date") != cutoff:
            raise BatchReductionError(
                "REDUCTION_CUTOFF_MISMATCH", security_id
            )
        templates[security_id] = str(
            stock_manifest.get("industry_template") or ""
        )
        stock_manifests.append(stock_manifest)
        annual_frames.append(
            _read_csv(
                stock_dir / "financial_annual.csv",
                columns=ANNUAL_COLUMNS,
            )
        )
        quarterly_frames.append(
            _read_csv(
                stock_dir / "financial_quarterly.csv",
                columns=QUARTERLY_COLUMNS,
            )
        )
        status_frames.append(
            _read_csv(
                stock_dir / "financial_field_status.csv",
                columns=STATUS_COLUMNS,
            )
        )
        gap_frames.append(_read_csv(stock_dir / "data_gaps.csv"))
        future_frames.append(
            _read_csv(stock_dir / "future_available_rows.csv")
        )
        duplicate_frames.append(
            _read_csv(stock_dir / "duplicate_resolution.csv")
        )
    annual = _concat(annual_frames, columns=ANNUAL_COLUMNS)
    quarterly = _concat(quarterly_frames, columns=QUARTERLY_COLUMNS)
    field_status = _concat(status_frames, columns=STATUS_COLUMNS)
    data_gaps = _concat(gap_frames)
    future_rows = _concat(future_frames)
    duplicate_resolution = _concat(duplicate_frames)
    successful_ids = {str(item["security_id"]) for item in successful}
    _validate_formal(
        annual,
        label="annual",
        cutoff=cutoff,
        successful_ids=successful_ids,
        request_by_id=request_by_id,
    )
    _validate_formal(
        quarterly,
        label="quarterly",
        cutoff=cutoff,
        successful_ids=successful_ids,
        request_by_id=request_by_id,
    )
    failure_gaps = [
        {
            "security_id": item.get("security_id"),
            "security_code": item.get("stock_code"),
            "report_period": "",
            "field_name": "",
            "status": item.get("status"),
            "reason": item.get("message")
            or item.get("error_code")
            or "batch stock did not complete",
            "source_url": "",
        }
        for item in failed + deferred
    ]
    if failure_gaps:
        data_gaps = _concat([data_gaps, pd.DataFrame(failure_gaps)])
    coverage = _coverage(field_status, templates)
    completed_ledger = _ledger(stocks, SUCCESS_STATUSES)
    failed_ledger = _ledger(stocks, FAILED_STATUSES)
    deferred_ledger = _ledger(stocks, DEFERRED_STATUSES)
    _write_csv(
        annual,
        output / "financial_annual.csv",
        columns=ANNUAL_COLUMNS,
    )
    _write_csv(
        quarterly,
        output / "financial_quarterly.csv",
        columns=QUARTERLY_COLUMNS,
    )
    _write_csv(
        field_status,
        output / "financial_field_status.csv",
        columns=STATUS_COLUMNS,
    )
    _write_csv(data_gaps, output / "data_gaps.csv")
    _write_csv(future_rows, output / "future_available_rows.csv")
    _write_csv(
        duplicate_resolution,
        output / "duplicate_resolution.csv",
    )
    _write_csv(coverage, output / "field_coverage.csv")
    _write_csv(
        completed_ledger,
        output / "completed_securities.csv",
        columns=LEDGER_COLUMNS,
    )
    _write_csv(
        failed_ledger,
        output / "failed_securities.csv",
        columns=LEDGER_COLUMNS,
    )
    _write_csv(
        deferred_ledger,
        output / "deferred_securities.csv",
        columns=LEDGER_COLUMNS,
    )
    if any(
        item.get("status") in {"FAILED_TERMINAL", "BLOCKED"}
        for item in stocks
    ):
        status = "FAILED_TERMINAL"
    elif failed or deferred:
        status = "FAILED_RECOVERABLE"
    elif any(
        item.get("status") == "COMPLETED_WITH_GAPS" for item in stocks
    ) or not data_gaps.empty:
        status = "PASS_WITH_GAPS"
    else:
        status = "PASS"
    validation = {
        "schema_version": 1,
        "status": status,
        "batch_id": batch_id,
        "as_of_date": cutoff,
        "input_count": len(rows),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "deferred_count": len(deferred),
        "annual_rows": len(annual),
        "quarterly_rows": len(quarterly),
        "field_status_rows": len(field_status),
        "data_gap_rows": len(data_gaps),
        "future_rows": len(future_rows),
        "duplicate_resolution_rows": len(duplicate_resolution),
        "conservation_pass": len(successful) + len(failed) + len(deferred)
        == len(rows),
        "formal_future_rows": 0,
        "errors": [],
    }
    validation_path = output / "validation_report.json"
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_files = [
        "financial_annual.csv",
        "financial_quarterly.csv",
        "financial_field_status.csv",
        "completed_securities.csv",
        "failed_securities.csv",
        "deferred_securities.csv",
        "data_gaps.csv",
        "future_available_rows.csv",
        "duplicate_resolution.csv",
        "field_coverage.csv",
        "validation_report.json",
        "checkpoint.json",
    ]
    hashes = {name: _file_sha256(output / name) for name in output_files}
    batch_manifest = {
        "schema_version": 1,
        "status": status,
        "batch_id": batch_id,
        "as_of_date": cutoff,
        "package_sha256": str(
            getattr(resolved, "package_sha256", "") or ""
        ),
        "selected_batch_sha256": str(
            getattr(resolved, "selected_batch_sha256", "") or ""
        ),
        "input_count": len(rows),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "deferred_count": len(deferred),
        "stock_manifest_fingerprints": {
            str(item["security_id"]): str(item.get("fingerprint") or "")
            for item in stock_manifests
        },
        "output_sha256": hashes,
        "fixture_mode": False,
    }
    manifest_path = output / "batch_manifest.json"
    manifest_path.write_text(
        json.dumps(batch_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return BatchReductionResult(
        status=status,
        batch_id=batch_id,
        output_dir=str(output),
        input_count=len(rows),
        successful_count=len(successful),
        failed_count=len(failed),
        deferred_count=len(deferred),
        annual_rows=len(annual),
        quarterly_rows=len(quarterly),
        field_status_rows=len(field_status),
        data_gap_rows=len(data_gaps),
        validation_report_path=str(validation_path),
        batch_manifest_path=str(manifest_path),
    )
