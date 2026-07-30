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
from ashare_f10.ascope_bridge.finance import FinanceExportResult, build_financial_tables
from ashare_f10.ascope_bridge.single_stock import (
    SingleStockExportError,
    export_single_stock,
)

INCOME_CUMULATIVE = "RPT_F10_FINANCE_GINCOME"
INCOME_STANDALONE = "RPT_F10_FINANCE_GINCOMEQC"
CASHFLOW_CUMULATIVE = "RPT_F10_FINANCE_GCASHFLOW"
CASHFLOW_STANDALONE = "RPT_F10_FINANCE_GCASHFLOWQC"
BALANCE = "RPT_F10_FINANCE_GBALANCE"
MAIN_FINANCE = "RPT_F10_FINANCE_MAINFINADATA"
QUARTER_MAIN_FINANCE = "RPT_F10_QTR_MAINFINADATA"

STANDALONE_FAMILIES = frozenset(
    {
        INCOME_STANDALONE,
        CASHFLOW_STANDALONE,
        QUARTER_MAIN_FINANCE,
    }
)

INCOME_KEYS = frozenset(
    {
        "OPERATE_INCOME",
        "TOTAL_OPERATE_INCOME",
        "OPERATE_COST",
        "TOTAL_OPERATE_COST",
        "DEDUCT_PARENT_NETPROFIT",
        "DEDU_PARENT_PROFIT",
    }
)
MAIN_FINANCE_KEYS = frozenset({"KCFJCXSYJLR"})
CASHFLOW_KEYS = frozenset({"NETCASH_OPERATE", "CONSTRUCT_LONG_ASSET"})
BALANCE_KEYS = frozenset(
    {
        "ACCOUNTS_RECE",
        "ACCOUNTS_RECEIVABLE",
        "INVENTORY",
        "CONTRACT_LIAB",
        "CONTRACT_LIABILITY",
        "CONTRACT_LIABILITIES",
        "INTEREST_BEARING_DEBT",
        "TOTAL_EQUITY",
        "TOTAL_EQUITY_PARENT",
        "TOTAL_ASSETS",
        "MONETARYFUNDS",
        "CASH_AND_DEPOSIT_CENTRAL_BANK",
        "SHORT_LOAN",
        "LONG_LOAN",
        "NONCURRENT_LIAB_1YEAR",
        "BOND_PAYABLE",
        "LEASE_LIAB",
    }
)
AUDIT_KEYS = frozenset({"AUDIT_OPINION", "OPINION_TYPE", "AUDIT_RESULT"})
INTERNAL_CONTROL_KEYS = frozenset(
    {"INTERNAL_CONTROL_OPINION", "INTERNAL_CONTROL_AUDIT_OPINION"}
)

ALLOWED_FAMILIES_BY_KEY: dict[str, frozenset[str]] = {
    **{
        key: frozenset({INCOME_CUMULATIVE, INCOME_STANDALONE})
        for key in INCOME_KEYS
    },
    **{
        key: frozenset({MAIN_FINANCE, QUARTER_MAIN_FINANCE})
        for key in MAIN_FINANCE_KEYS
    },
    **{
        key: frozenset({CASHFLOW_CUMULATIVE, CASHFLOW_STANDALONE})
        for key in CASHFLOW_KEYS
    },
    **{key: frozenset({BALANCE}) for key in BALANCE_KEYS},
    **{key: frozenset({INCOME_CUMULATIVE}) for key in AUDIT_KEYS},
    # No current F10 family is trusted for the internal-control opinion. Keep the
    # canonical column and emit SOURCE_MISSING until a point-in-time official
    # metadata adapter is added; never infer it from the audit opinion.
    **{key: frozenset() for key in INTERNAL_CONTROL_KEYS},
}

FAMILY_PRIORITY = {
    INCOME_CUMULATIVE: 100,
    INCOME_STANDALONE: 100,
    CASHFLOW_CUMULATIVE: 100,
    CASHFLOW_STANDALONE: 100,
    BALANCE: 100,
    MAIN_FINANCE: 80,
    QUARTER_MAIN_FINANCE: 80,
}


def _has_source_value(frame: pd.DataFrame) -> pd.Series:
    numeric = (
        frame["value_num"].notna()
        if "value_num" in frame.columns
        else pd.Series(False, index=frame.index)
    )
    if "value_text" not in frame.columns:
        return numeric
    text = frame["value_text"].notna() & (
        frame["value_text"].astype(str).str.strip() != ""
    )
    return numeric | text


def select_canonical_source_facts(facts: pd.DataFrame) -> pd.DataFrame:
    """Select only semantically valid source families for A-SCOPE fields.

    Eastmoney ratio and Dupont datasets reuse statement field keys for percentages
    and composition ratios. Selecting by field key alone therefore mixes values such
    as TOTAL_ASSETS=100 with the actual balance-sheet amount. This selector binds each
    canonical key to its authoritative statement family, marks QC families as direct
    standalone-quarter sources and removes empty duplicates before mapping.
    """

    if facts.empty or "field_key" not in facts.columns or "family" not in facts.columns:
        return facts.iloc[0:0].copy()

    selected = facts.copy()
    selected["field_key"] = selected["field_key"].fillna("").astype(str).str.upper()
    selected["family"] = selected["family"].fillna("").astype(str).str.upper()
    allowed = pd.Series(False, index=selected.index)
    for key, families in ALLOWED_FAMILIES_BY_KEY.items():
        if families:
            allowed |= (selected["field_key"] == key) & selected["family"].isin(families)
    selected = selected[allowed & _has_source_value(selected)].copy()
    if selected.empty:
        return selected

    selected["period_basis"] = selected["family"].map(
        lambda family: "STANDALONE" if family in STANDALONE_FAMILIES else "CUMULATIVE"
    )
    selected["source_priority"] = selected["family"].map(FAMILY_PRIORITY).fillna(0).astype(int)

    dedupe_columns = [
        column
        for column in (
            "security_code",
            "family",
            "record_key",
            "report_date",
            "available_at",
            "period_basis",
            "field_key",
            "value_num",
            "value_text",
            "unit",
        )
        if column in selected.columns
    ]
    return selected.drop_duplicates(dedupe_columns, keep="last").reset_index(drop=True)


def build_canonical_financial_tables(
    facts: pd.DataFrame,
    **kwargs: Any,
) -> FinanceExportResult:
    return build_financial_tables(select_canonical_source_facts(facts), **kwargs)


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
