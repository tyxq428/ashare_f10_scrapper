from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.ascope_bridge.batch import (
    StockProcessResult,
    _normalize_result,
    _retryable_text,
)
from ashare_f10.ascope_bridge.finance import (
    DEBT_COMPONENTS,
    FIELD_SPECS,
    FinanceExportResult,
    build_financial_tables,
)
from ashare_f10.ascope_bridge.single_stock import (
    SingleStockExportError,
    export_single_stock,
)

CANONICAL_SOURCE_KEYS = frozenset(
    {
        *(key for spec in FIELD_SPECS for key in spec.keys),
        *DEBT_COMPONENTS,
    }
)


def build_canonical_financial_tables(
    facts: pd.DataFrame,
    **kwargs: Any,
) -> FinanceExportResult:
    """Limit the A-SCOPE bridge to source fields used by its canonical schema.

    The base F10 fact store intentionally contains every page field. Feeding all of
    those facts into the finance mapper creates one availability gap for every
    unrelated holding, news, governance and event field. Filtering here preserves
    the complete normalized F10 store while keeping the A-SCOPE export bounded to
    its declared financial data contract.
    """

    selected = facts.copy()
    if "field_key" in selected.columns:
        keys = selected["field_key"].fillna("").astype(str).str.upper()
        selected = selected[keys.isin(CANONICAL_SOURCE_KEYS)].copy()
    return build_financial_tables(selected, **kwargs)


def canonical_stock_processor(
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
            mapper=build_canonical_financial_tables,
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
    heartbeat = max(1, int(float(context.get("heartbeat_seconds", 30))))
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
        str(heartbeat),
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
            mapper=build_canonical_financial_tables,
        )
        return _normalize_result(result)
    except SingleStockExportError as exc:
        return StockProcessResult(
            status="FAILED_TERMINAL",
            error_code=exc.code,
            message=exc.message,
        )
