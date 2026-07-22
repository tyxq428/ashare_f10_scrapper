from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.derived import evaluate_simple_formula
from ashare_f10.cross_validation.registry import FieldValidationRegistry
from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.models import OfficialDocument, TargetField


def test_dupont_blank_unit_monetary_fact_uses_numeric_policy() -> None:
    east = pd.DataFrame(
        [
            {
                "security_code": "002352",
                "theme": "财务分析",
                "family": "RPT_F10_FINANCE_DUPONT",
                "dataset": "dupont",
                "record_key": "002352|dupont|2025-12-31",
                "report_date": "2025-12-31",
                "event_date": "2025-12-31",
                "period_type": "FY",
                "statement_type": "dupont",
                "scope": "consolidated",
                "data_semantics": "event",
                "field_key": "NETPROFIT",
                "field_name_cn": "净利润",
                "field_category": "PAGE_DISPLAY_FIELD",
                "value_num": 11_684_811_000.0,
                "value_text": "11684811000",
                "unit": "",
                "source_url": "https://eastmoney.invalid/dupont",
            }
        ]
    )
    registry = FieldValidationRegistry.load().build_frame(east)
    entry = registry.iloc[0]
    assert entry["validation_mode"] == "OFFICIAL_DERIVED"
    assert entry["comparison_method"] == "numeric"

    official = pd.DataFrame(
        [
            {
                "security_code": "002352",
                "report_date": "2025-12-31",
                "period_type": "FY",
                "statement_type": "dupont",
                "scope": "consolidated",
                "field_key": "NETPROFIT",
                "value_num": 11_684_811_000.0,
                "value_text": "11684811000.0",
                "unit": "元",
                "normalized_unit": "元",
                "precision_tolerance": 1.0,
                "source_document": "2025年年度报告",
                "source_url": "https://cninfo.invalid/report.pdf",
                "source_page": 88,
                "source_row": "净利润 11,684,811,000.00",
            }
        ]
    )
    result = CrossSourceComparator(registry).compare(east, official).iloc[0]
    assert result["status"] == "DERIVED_MATCH"
    assert result["root_cause"] == "VALUE_MATCH"
    assert result["difference"] == 0.0


def test_quick_ratio_formula_matches_cninfo_disclosed_definition() -> None:
    formula = FieldValidationRegistry.load().formulas["GUARD_SPEED_RATIO"]
    values = {
        "TOTAL_CURRENT_ASSETS": 91_327_047_000.0,
        "INVENTORY": 3_039_030_000.0,
        "PREPAYMENT": 2_907_746_000.0,
        "OTHER_CURRENT_ASSET": 9_620_165_000.0,
        "CONTRACT_ASSET": 3_049_117_000.0,
        "FINANCE_RECE": 244_734_000.0,
        "CURRENT_ASSET_OTHER": 328_146_000.0,
        "NONCURRENT_ASSET_1YEAR": 45_164_000.0,
        "TOTAL_CURRENT_LIAB": 72_894_721_000.0,
    }
    result = evaluate_simple_formula(formula, values)
    assert abs(result - 0.989000904469) < 1e-12


def test_cninfo_eps_row_unit_is_not_scaled_by_page_thousand_yuan() -> None:
    target = TargetField(
        "BASIC_EPS",
        "基本每股收益",
        "summary",
        ("基本每股收益",),
        ("BASIC_EPS",),
        ("RPT_F10_FINANCE_MAINFINADATA",),
    )
    document = OfficialDocument(
        "CNINFO",
        "002352",
        "2026年一季度报告",
        "2026-04-29",
        "2026-03-31",
        "q1",
        "original",
        "https://cninfo.invalid/q1.pdf",
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        "基本每股收益（元/股） 0.51 0.45 13.33%",
        target,
        document,
        2,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 0.51
    assert fact.unit == "元/股"
    assert fact.normalized_unit == "元/股"
