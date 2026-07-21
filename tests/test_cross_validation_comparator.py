from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.registry import FieldValidationRegistry


def _eastmoney() -> pd.DataFrame:
    common = {
        "security_code": "688521",
        "dataset": "财务 / RPT_F10_FINANCE_GBALANCE",
        "record_key": "688521|RPT_F10_FINANCE_GBALANCE|2025-12-31",
        "report_date": "2025-12-31",
        "event_date": None,
        "period_type": "FY",
        "data_semantics": "point_in_time",
        "field_category": "PAGE_DISPLAY_FIELD",
        "source_url": "https://eastmoney.example",
    }
    return pd.DataFrame(
        [
            {
                **common,
                "theme": "财务",
                "family": "RPT_F10_FINANCE_GBALANCE",
                "field_key": "TOTAL_ASSETS",
                "field_name_cn": "资产总计",
                "value_num": 1000.0,
                "value_text": "1000",
                "unit": "元",
                "statement_type": "balance_sheet",
                "scope": "consolidated",
            },
            {
                **common,
                "theme": "行情",
                "family": "/api/qt/stock/get",
                "dataset": "最新行情",
                "record_key": "688521|quote",
                "report_date": None,
                "event_date": "2026-07-21",
                "field_key": "f43",
                "field_name_cn": "最新价",
                "value_num": 120.0,
                "value_text": "120",
                "unit": "元",
                "statement_type": "",
                "scope": "entity",
            },
        ]
    )


def _official() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "security_code": "688521",
                "report_date": "2025-12-31",
                "statement_type": "balance_sheet",
                "scope": "consolidated",
                "field_key": "TOTAL_ASSETS",
                "field_name_cn": "资产总计",
                "value_num": 1000.0,
                "value_text": "1000",
                "unit": "元",
                "normalized_unit": "元",
                "precision_tolerance": 1.0,
                "source_document": "2025年年度报告",
                "source_url": "https://sse.example/report.pdf",
                "source_page": 100,
                "source_row": "资产总计 1000",
                "theme": "官方披露/资产负债表",
                "family": "OFFICIAL_DISCLOSURE",
                "dataset": "2025年年度报告",
                "record_key": "official",
                "event_date": None,
                "period_type": "FY",
                "data_semantics": "point_in_time",
                "field_category": "PAGE_DISPLAY_FIELD",
                "source_status": "FACT_DIRECT",
            }
        ]
    )


def test_non_periodic_fact_is_not_a_mismatch() -> None:
    east = _eastmoney()
    registry_engine = FieldValidationRegistry.load()
    registry = registry_engine.build_frame(east)
    compared = CrossSourceComparator(registry).compare(east, _official())
    assert compared.loc[compared.field_key == "TOTAL_ASSETS", "status"].item() == "EXACT_MATCH"
    assert compared.loc[compared.field_key == "f43", "status"].item() == "NOT_IN_OFFICIAL_SCOPE"
    assert not (compared.status == "MISMATCH").any()


def test_metadata_dates_and_report_labels_are_normalized():
    from ashare_f10.cross_validation.comparator import _normalize_text

    assert _normalize_text("2025-12-31 00:00:00", "REPORT_DATE") == "2025-12-31"
    assert _normalize_text("2025年年度报告", "REPORT_DATE_NAME") == "fy"
    assert _normalize_text("2025年报", "REPORT_DATE_NAME") == "fy"
    assert _normalize_text("四季度", "REPORT_TYPE") == "q4"
    assert _normalize_text("2025三季报", "REPORT_DATE_NAME") == "q3c"
    assert _normalize_text("2025三季度", "REPORT_DATE_NAME") == "q3"
