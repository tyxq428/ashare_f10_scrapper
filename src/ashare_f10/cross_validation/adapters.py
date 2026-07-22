from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

FINANCIAL_STATEMENT_FAMILY_MAP = {
    "RPT_F10_FINANCE_GBALANCE": "balance_sheet",
    "RPT_F10_FINANCE_GINCOME": "income_statement",
    "RPT_F10_FINANCE_GCASHFLOW": "cash_flow",
    "RPT_F10_FINANCE_GINCOMEQC": "income_statement",
    "RPT_F10_FINANCE_GCASHFLOWQC": "cash_flow",
    "RPT_F10_FINANCE_MAINFINADATA": "financial_indicator",
    "RPT_F10_QTR_MAINFINADATA": "financial_indicator",
    "RPT_F10_FINANCE_GRATIO": "financial_ratio",
    "RPT_F10_FINANCE_QGRATIO": "financial_ratio",
    "RPT_F10_FINANCE_DUPONT": "dupont",
}


def canonical_period_type(report_date: Any, family: str = "", explicit: Any = None) -> str:
    text = str(report_date or "")[:10]
    month = text[5:7] if len(text) >= 7 else ""
    label = str(explicit or "").strip().upper()
    independent = family in {
        "RPT_F10_FINANCE_GINCOMEQC",
        "RPT_F10_FINANCE_GCASHFLOWQC",
        "RPT_F10_QTR_MAINFINADATA",
        "RPT_F10_FINANCE_QGRATIO",
    }
    if any(token in label for token in ("一季度", "一季报", "Q1")) or month == "03":
        return "Q1"
    if independent:
        if any(token in label for token in ("二季度", "Q2")) or month == "06":
            return "Q2"
        if any(token in label for token in ("三季度", "Q3")) or month == "09":
            return "Q3"
        if any(token in label for token in ("四季度", "Q4")) or month == "12":
            return "Q4"
    if any(token in label for token in ("半年", "中报", "H1")) or month == "06":
        return "H1"
    if any(token in label for token in ("三季报", "前三季度", "Q3C")) or month == "09":
        return "Q3C"
    if any(token in label for token in ("年报", "年度", "FY")) or month == "12":
        return "FY"
    return label or "OTHER"


def _plain_collection(value: Any) -> Any:
    """Convert Arrow/Numpy collection scalars into JSON-safe Python collections."""

    if value is None:
        return []
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if converted is not None else []
    if isinstance(value, tuple):
        return list(value)
    return value


def load_eastmoney_facts(db_path: Path | str) -> pd.DataFrame:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        frame = connection.execute("SELECT * FROM facts").fetch_df()
    finally:
        connection.close()
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["period_type"] = frame.apply(
        lambda row: canonical_period_type(
            row.get("report_date"), str(row.get("family") or ""), row.get("period_type")
        ),
        axis=1,
    )
    frame["source"] = "EASTMONEY"
    frame["statement_type"] = frame["family"].map(FINANCIAL_STATEMENT_FAMILY_MAP).fillna("")
    frame["scope"] = frame["statement_type"].map(lambda value: "consolidated" if value else "entity")
    frame["normalized_unit"] = frame["unit"].fillna("")

    monetary_override = (frame["family"] == "RPT_F10_FINANCE_GBALANCE") & frame["field_key"].isin(
        {"TREASURY_SHARES"}
    )
    frame.loc[monetary_override, "unit"] = "元"
    frame.loc[monetary_override, "normalized_unit"] = "元"
    frame["source_document"] = frame["family"]
    frame["source_page"] = None
    frame["source_row"] = frame.get("record_key", "")
    frame["precision_tolerance"] = None
    frame["confidence"] = "high"
    return frame


def load_official_facts(parquet_path: Path | str, *, include_suspect: bool = False) -> pd.DataFrame:
    frame = pd.read_parquet(parquet_path)
    if frame.empty:
        return frame
    frame = frame.copy()
    if "source_status" not in frame:
        frame["source_status"] = "FACT_DIRECT"
    else:
        frame["source_status"] = frame["source_status"].fillna("FACT_DIRECT")
    if "quality_flags" in frame:
        frame["quality_flags"] = frame["quality_flags"].map(_plain_collection)
    if not include_suspect:
        frame = frame[~frame["source_status"].isin({"PARSE_SUSPECT", "UNRESOLVED"})].copy()
    frame["source"] = "OFFICIAL_DISCLOSURE"
    frame["family"] = "OFFICIAL_DISCLOSURE"
    frame["theme"] = (
        frame["statement_type"]
        .map(
            {
                "balance_sheet": "官方披露/资产负债表",
                "income_statement": "官方披露/利润表",
                "cash_flow": "官方披露/现金流量表",
                "summary": "官方披露/摘要",
            }
        )
        .fillna("官方披露")
    )
    frame["dataset"] = frame["source_document"]
    frame["record_key"] = (
        frame["security_code"].astype(str)
        + "|"
        + frame["report_date"].astype(str)
        + "|"
        + frame["statement_type"].astype(str)
        + "|"
        + frame["field_key"].astype(str)
    )
    frame["event_date"] = None
    frame["period_type"] = frame["report_date"].map(canonical_period_type)
    frame["data_semantics"] = (
        frame["statement_type"]
        .map(
            {
                "balance_sheet": "point_in_time",
                "income_statement": "flow",
                "cash_flow": "flow",
            }
        )
        .fillna("event")
    )
    frame["field_name_cn"] = frame["field_name_report"]
    frame["field_category"] = "PAGE_DISPLAY_FIELD"
    frame["value_num"] = frame["value"]
    frame["value_text"] = frame["value"].map(lambda value: None if pd.isna(value) else str(value))
    frame["source_url"] = frame["source_url"].fillna("")
    return frame


def official_fact_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "security_code",
        "theme",
        "family",
        "dataset",
        "record_key",
        "report_date",
        "event_date",
        "period_type",
        "statement_type",
        "scope",
        "data_semantics",
        "field_key",
        "field_name_cn",
        "field_category",
        "value_text",
        "value_num",
        "unit",
        "normalized_unit",
        "source_url",
        "source_document",
        "source_page",
        "source_row",
        "precision_tolerance",
        "confidence",
        "source_status",
        "quality_flags",
        "parse_notes",
        "raw_value",
        "document_id",
        "effective_at",
        "available_at",
        "extracted_at",
    ]
    for column in columns:
        if column not in frame:
            frame[column] = None
    return frame[columns]
