from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from ashare_f10.ascope_bridge.single_stock import (
    SingleStockExportError,
    export_single_stock,
)

TERMINAL_SUCCESS = {"COMPLETED", "COMPLETED_WITH_GAPS"}
RESUMABLE = {
    "PENDING",
    "FAILED_RETRYABLE",
    "DEFERRED_TIME_BUDGET",
    "FETCHING",
    "EXPORTING",
}
TERMINAL_FAILURE = {"FAILED_TERMINAL", "BLOCKED"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class BatchExecutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class StockProcessResult:
    status: str
    retryable: bool = False
    error_code: str = ""
    message: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BatchRunResult:
    status: str
    batch_id: str
    output_dir: str
    checkpoint_path: str
    input_count: int
    completed_count: int
    completed_with_gaps_count: int
    failed_retryable_count: int
    failed_terminal_count: int
    deferred_count: int
    fingerprint: str

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
        if hasattr(row, name)
    }


def _json_fingerprint(value: Any) -> str:
    import hashlib

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolved_parts(
    resolved: Any,
) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
    batch_id = str(getattr(resolved, "batch_id", "") or "")
    rows = [_row_dict(row) for row in getattr(resolved, "rows", ())]
    manifest = getattr(resolved, "manifest", None)
    cutoff = str(
        getattr(manifest, "through", "")
        or (rows[0].get("request_through") if rows else "")
    )
    identity = {
        "batch_id": batch_id,
        "cutoff": cutoff,
        "package_sha256": str(getattr(resolved, "package_sha256", "") or ""),
        "selected_batch_sha256": str(
            getattr(resolved, "selected_batch_sha256", "") or ""
        ),
        "source_row_count": int(
            getattr(resolved, "source_row_count", len(rows)) or len(rows)
        ),
        "smoke_count": int(getattr(resolved, "smoke_count", 0) or 0),
        "rows": rows,
    }
    if not batch_id or not rows or not cutoff:
        raise BatchExecutionError(
            "BATCH_REQUEST_INVALID", "batch_id, rows and cutoff are required"
        )
    return batch_id, cutoff, rows, identity


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _initial_state(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "request": row,
        "security_id": str(row["security_id"]),
        "stock_code": str(row["code"]).zfill(6),
        "stock_name": str(row.get("name") or ""),
        "status": "PENDING",
        "attempt_count": 0,
        "started_at_utc": None,
        "completed_at_utc": None,
        "updated_at_utc": utc_now(),
        "retryable": False,
        "error_code": "",
        "message": "",
        "details": {},
    }


def _load_checkpoint(
    path: Path,
    *,
    fingerprint: str,
    rows: list[dict[str, Any]],
    batch_id: str,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "batch_id": batch_id,
            "fingerprint": fingerprint,
            "status": "RUNNING",
            "created_at_utc": utc_now(),
            "updated_at_utc": utc_now(),
            "stocks": [_initial_state(row) for row in rows],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchExecutionError("CHECKPOINT_INVALID", str(path)) from exc
    if value.get("fingerprint") != fingerprint or value.get("batch_id") != batch_id:
        raise BatchExecutionError("CHECKPOINT_FINGERPRINT_MISMATCH", str(path))
    expected = [str(row["security_id"]) for row in rows]
    actual = [str(item.get("security_id") or "") for item in value.get("stocks", [])]
    if actual != expected:
        raise BatchExecutionError(
            "CHECKPOINT_REQUEST_MISMATCH", "security order or identity changed"
        )
    for item in value.get("stocks", []):
        if item.get("status") in {"FETCHING", "EXPORTING"}:
            item["status"] = "FAILED_RETRYABLE"
            item["retryable"] = True
            item["error_code"] = "INTERRUPTED_IN_FLIGHT"
            item["message"] = "Previous execution stopped while the stock was in flight"
    return value


def _normalize_result(value: Any) -> StockProcessResult:
    if isinstance(value, StockProcessResult):
        return value
    if hasattr(value, "status"):
        status = (
            "COMPLETED_WITH_GAPS"
            if str(value.status) == "PASS_WITH_GAPS"
            else "COMPLETED"
        )
        return StockProcessResult(
            status=status,
            details=getattr(value, "to_dict", lambda: {})(),
        )
    if isinstance(value, Mapping):
        status = str(value.get("status") or "").upper()
        if status in {"PASS", "CACHE_HIT", "COMPLETED"}:
            status = "COMPLETED"
        elif status in {"PASS_WITH_GAPS", "COMPLETED_WITH_GAPS"}:
            status = "COMPLETED_WITH_GAPS"
        if status not in TERMINAL_SUCCESS | {
            "FAILED_RETRYABLE",
            "FAILED_TERMINAL",
            "BLOCKED",
        }:
            raise BatchExecutionError(
                "PROCESSOR_RESULT_INVALID", f"status={status!r}"
            )
        return StockProcessResult(
            status=status,
            retryable=bool(value.get("retryable", status == "FAILED_RETRYABLE")),
            error_code=str(value.get("error_code") or ""),
            message=str(value.get("message") or ""),
            details=dict(value.get("details") or {}),
        )
    raise BatchExecutionError("PROCESSOR_RESULT_INVALID", type(value).__name__)


def _retryable_text(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "429",
            "timeout",
            "timed out",
            "connection",
            "temporary",
            "http 5",
            "request groups failed",
            "failed group",
        )
    )


def default_stock_processor(
    request: dict[str, Any],
    attempt: int,
    context: dict[str, Any],
) -> StockProcessResult:
    data_root = Path(context["data_root"])
    stock_output_root = Path(context["stock_output_root"])
    cutoff = str(context["as_of_date"])
    try:
        result = export_single_stock(
            request,
            data_root=data_root,
            output_root=stock_output_root,
            as_of_date=cutoff,
        )
        return _normalize_result(result)
    except SingleStockExportError as exc:
        if exc.code not in {
            "CURRENT_RUN_NOT_FOUND",
            "CURRENT_RUN_DIRECTORY_NOT_FOUND",
            "SOURCE_FACTS_NOT_FOUND",
        }:
            return StockProcessResult(
                status="FAILED_TERMINAL",
                error_code=exc.code,
                message=exc.message,
            )
    run_dir = (
        Path(context["batch_output_dir"])
        / "_f10_runs"
        / str(request["security_id"])
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[3] / "scripts" / "run_resilient_fetch.py"
    report = run_dir / "resilient-fetch-report.json"
    command = [
        sys.executable,
        str(script),
        str(request["code"]),
        "--output",
        str(run_dir),
        "--workers",
        str(context.get("endpoint_workers", 4)),
        "--max-attempts",
        "1",
        "--backoff-seconds",
        "8",
        "--heartbeat-seconds",
        str(context.get("heartbeat_seconds", 30)),
        "--report",
        str(report),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        reason = f"resilient fetch exit code {completed.returncode}"
        if report.exists():
            try:
                value = json.loads(report.read_text(encoding="utf-8"))
                reason = str(value.get("failure_reason") or reason)
            except (OSError, json.JSONDecodeError):
                pass
        retryable = _retryable_text(reason)
        return StockProcessResult(
            status="FAILED_RETRYABLE" if retryable else "FAILED_TERMINAL",
            retryable=retryable,
            error_code="F10_FETCH_FAILED",
            message=reason,
            details={"attempt": attempt, "report": str(report)},
        )
    try:
        result = export_single_stock(
            request,
            data_root=data_root,
            output_root=stock_output_root,
            as_of_date=cutoff,
            source_run_dir=run_dir,
        )
        return _normalize_result(result)
    except SingleStockExportError as exc:
        return StockProcessResult(
            status="FAILED_TERMINAL",
            error_code=exc.code,
            message=exc.message,
        )


def _process_with_attempts(
    state: dict[str, Any],
    *,
    processor: Callable[[dict[str, Any], int, dict[str, Any]], Any],
    context: dict[str, Any],
    max_attempts: int,
    deadline: float | None,
    clock: Callable[[], float],
) -> dict[str, Any]:
    result = dict(state)
    result["started_at_utc"] = result.get("started_at_utc") or utc_now()
    start_attempt = int(result.get("attempt_count") or 0) + 1
    for attempt in range(start_attempt, max_attempts + 1):
        if deadline is not None and clock() >= deadline:
            result.update(
                status="DEFERRED_TIME_BUDGET",
                retryable=True,
                error_code="TIME_BUDGET_REACHED",
                message="Soft deadline reached before another stock attempt",
                updated_at_utc=utc_now(),
            )
            return result
        result["attempt_count"] = attempt
        try:
            outcome = _normalize_result(
                processor(dict(result["request"]), attempt, context)
            )
        except Exception as exc:  # noqa: BLE001
            retryable = bool(getattr(exc, "retryable", False))
            outcome = StockProcessResult(
                status="FAILED_RETRYABLE" if retryable else "FAILED_TERMINAL",
                retryable=retryable,
                error_code=str(getattr(exc, "code", "PROCESSOR_EXCEPTION")),
                message=str(exc),
            )
        result.update(
            status=outcome.status,
            retryable=outcome.retryable,
            error_code=outcome.error_code,
            message=outcome.message,
            details=outcome.details or {},
            updated_at_utc=utc_now(),
        )
        if outcome.status in TERMINAL_SUCCESS | TERMINAL_FAILURE:
            result["completed_at_utc"] = utc_now()
            return result
        if outcome.status != "FAILED_RETRYABLE" or not outcome.retryable:
            result["status"] = "FAILED_TERMINAL"
            result["completed_at_utc"] = utc_now()
            return result
    result["status"] = "FAILED_RETRYABLE"
    result["retryable"] = True
    result["completed_at_utc"] = utc_now()
    return result


def _write_ledgers(output_dir: Path, stocks: list[dict[str, Any]]) -> None:
    columns = (
        "security_id",
        "stock_code",
        "stock_name",
        "status",
        "attempt_count",
        "error_code",
        "message",
        "updated_at_utc",
    )
    groups = {
        "completed_securities.csv": TERMINAL_SUCCESS,
        "failed_securities.csv": {
            "FAILED_RETRYABLE",
            "FAILED_TERMINAL",
            "BLOCKED",
        },
        "deferred_securities.csv": {"DEFERRED_TIME_BUDGET"},
    }
    for filename, statuses in groups.items():
        rows = [
            {key: item.get(key) for key in columns}
            for item in stocks
            if item.get("status") in statuses
        ]
        pd.DataFrame(rows, columns=columns).to_csv(
            output_dir / filename, index=False, encoding="utf-8-sig"
        )


def _batch_status(stocks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in stocks}
    if statuses <= {"COMPLETED"}:
        return "PASS"
    if statuses <= TERMINAL_SUCCESS:
        return "PASS_WITH_GAPS"
    if statuses & {"FAILED_TERMINAL", "BLOCKED"}:
        return "FAILED_TERMINAL"
    return "FAILED_RECOVERABLE"


def run_batch(
    resolved: Any,
    *,
    data_root: Path | str,
    output_root: Path | str,
    max_stock_workers: int = 2,
    max_attempts: int = 2,
    soft_deadline_seconds: float = 0,
    heartbeat_seconds: float = 30,
    processor: Callable[
        [dict[str, Any], int, dict[str, Any]], Any
    ] = default_stock_processor,
    force_retry: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> BatchRunResult:
    if not 1 <= max_stock_workers <= 2:
        raise BatchExecutionError(
            "BATCH_CONCURRENCY_INVALID", str(max_stock_workers)
        )
    if not 1 <= max_attempts <= 2:
        raise BatchExecutionError("BATCH_ATTEMPTS_INVALID", str(max_attempts))
    batch_id, cutoff, rows, identity = _resolved_parts(resolved)
    fingerprint = _json_fingerprint(identity)
    batch_output = Path(output_root) / batch_id
    stock_output = batch_output / "stocks"
    checkpoint_path = batch_output / "checkpoint.json"
    checkpoint = _load_checkpoint(
        checkpoint_path,
        fingerprint=fingerprint,
        rows=rows,
        batch_id=batch_id,
    )
    if force_retry:
        for state in checkpoint["stocks"]:
            if state.get("status") in {
                "FAILED_RETRYABLE",
                "DEFERRED_TIME_BUDGET",
            }:
                state["status"] = "PENDING"
    start = clock()
    deadline = start + soft_deadline_seconds if soft_deadline_seconds > 0 else None
    context = {
        "data_root": str(Path(data_root)),
        "stock_output_root": str(stock_output),
        "batch_output_dir": str(batch_output),
        "as_of_date": cutoff,
        "endpoint_workers": 4,
        "heartbeat_seconds": heartbeat_seconds,
    }
    batch_output.mkdir(parents=True, exist_ok=True)
    checkpoint["status"] = "RUNNING"
    checkpoint["updated_at_utc"] = utc_now()
    _atomic_json(checkpoint_path, checkpoint)
    states_by_id = {
        str(item["security_id"]): item for item in checkpoint["stocks"]
    }
    pending = [
        item
        for item in checkpoint["stocks"]
        if item.get("status") in RESUMABLE
        and item.get("status") not in TERMINAL_SUCCESS | TERMINAL_FAILURE
    ]
    future_map: dict[Future, str] = {}
    with ThreadPoolExecutor(
        max_workers=max_stock_workers, thread_name_prefix="ascope-stock"
    ) as pool:
        for state in pending:
            if deadline is not None and clock() >= deadline:
                state.update(
                    status="DEFERRED_TIME_BUDGET",
                    retryable=True,
                    error_code="TIME_BUDGET_REACHED",
                    message="Soft deadline reached before the stock started",
                    updated_at_utc=utc_now(),
                )
                continue
            state["status"] = "FETCHING"
            state["updated_at_utc"] = utc_now()
            _atomic_json(checkpoint_path, checkpoint)
            future = pool.submit(
                _process_with_attempts,
                dict(state),
                processor=processor,
                context=context,
                max_attempts=max_attempts,
                deadline=deadline,
                clock=clock,
            )
            future_map[future] = str(state["security_id"])
        while future_map:
            done, _not_done = wait(
                future_map,
                timeout=max(0.1, heartbeat_seconds),
                return_when=FIRST_COMPLETED,
            )
            if not done:
                counts = pd.Series(
                    [str(item.get("status")) for item in checkpoint["stocks"]]
                ).value_counts().to_dict()
                print(
                    json.dumps(
                        {
                            "event": "ascope_batch_heartbeat",
                            "at_utc": utc_now(),
                            "batch_id": batch_id,
                            "counts": counts,
                            "active": len(future_map),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                continue
            for future in done:
                security_id = future_map.pop(future)
                states_by_id[security_id].update(future.result())
                checkpoint["updated_at_utc"] = utc_now()
                _atomic_json(checkpoint_path, checkpoint)
                print(
                    json.dumps(
                        {
                            "event": "ascope_stock_completed",
                            "at_utc": utc_now(),
                            "batch_id": batch_id,
                            "security_id": security_id,
                            "status": states_by_id[security_id]["status"],
                            "attempt_count": states_by_id[security_id][
                                "attempt_count"
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    checkpoint["status"] = _batch_status(checkpoint["stocks"])
    checkpoint["updated_at_utc"] = utc_now()
    _write_ledgers(batch_output, checkpoint["stocks"])
    _atomic_json(checkpoint_path, checkpoint)
    counts = pd.Series(
        [str(item.get("status")) for item in checkpoint["stocks"]]
    ).value_counts()
    result = BatchRunResult(
        status=str(checkpoint["status"]),
        batch_id=batch_id,
        output_dir=str(batch_output),
        checkpoint_path=str(checkpoint_path),
        input_count=len(rows),
        completed_count=int(counts.get("COMPLETED", 0)),
        completed_with_gaps_count=int(counts.get("COMPLETED_WITH_GAPS", 0)),
        failed_retryable_count=int(counts.get("FAILED_RETRYABLE", 0)),
        failed_terminal_count=int(
            counts.get("FAILED_TERMINAL", 0) + counts.get("BLOCKED", 0)
        ),
        deferred_count=int(counts.get("DEFERRED_TIME_BUDGET", 0)),
        fingerprint=fingerprint,
    )
    (batch_output / "batch_run_result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
