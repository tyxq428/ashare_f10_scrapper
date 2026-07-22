from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.comparison_policy import infer_comparison_policy
from ashare_f10.cross_validation.models import RegistryEntry


def _eastmoney_row(
    field_key: str,
    field_name: str,
    *,
    value_num: float | None = None,
    value_text: str | None = None,
    unit: str = "",
) -> dict:
    return {
        "security_code": "688521",
        "theme": "财务分析",
        "family": "RPT_F10_FINANCE_GINCOME",
        "dataset": "income",
        "record_key": f"2025|{field_key}",
        "report_date": "2025-12-31",
        "event_date": None,
        "period_type": "FY",
        "statement_type": "income_statement",
        "scope": "consolidated",
        "data_semantics": "flow",
        "field_key": field_key,
        "field_name_cn": field_name,
        "field_category": "PAGE_DISPLAY_FIELD",
        "value_num": value_num,
        "value_text": value_text,
        "unit": unit,
        "source_url": "https://eastmoney.invalid",
    }


def _official_row(
    field_key: str,
    field_name: str,
    *,
    value_num: float | None = None,
    value_text: str | None = None,
    unit: str = "",
    tolerance: float = 0.0,
) -> dict:
    return {
        "security_code": "688521",
        "theme": "官方披露/利润表",
        "family": "OFFICIAL_DISCLOSURE",
        "dataset": "2025年年度报告",
        "record_key": f"official|{field_key}",
        "report_date": "2025-12-31",
        "event_date": None,
        "period_type": "FY",
        "statement_type": "income_statement",
        "scope": "consolidated",
        "data_semantics": "flow",
        "field_key": field_key,
        "field_name_cn": field_name,
        "field_category": "PAGE_DISPLAY_FIELD",
        "value_num": value_num,
        "value_text": value_text,
        "unit": unit,
        "normalized_unit": unit,
        "source_url": "https://sse.invalid/report.pdf",
        "source_document": "2025年年度报告",
        "source_page": 80,
        "source_row": field_name,
        "precision_tolerance": tolerance,
        "confidence": "high",
        "source_status": "FACT_DIRECT",
    }


def _registry_entry(field_key: str, field_name: str, unit: str = "") -> RegistryEntry:
    policy = infer_comparison_policy(field_key, field_name, unit, "flow")
    return RegistryEntry(
        theme="财务分析",
        family="RPT_F10_FINANCE_GINCOME",
        dataset="income",
        field_key=field_key,
        field_name_cn=field_name,
        validation_mode="OFFICIAL_DIRECT",
        statement_type="income_statement",
        scope="consolidated",
        data_semantics="flow",
        unit=unit,
        comparison_method=policy.method,
        canonical_unit=policy.canonical_unit,
        absolute_tolerance=policy.absolute_tolerance,
        relative_tolerance=policy.relative_tolerance,
        display_decimals=policy.display_decimals,
    )


def _compare(entry: RegistryEntry, east: dict, official: dict) -> dict:
    comparator = CrossSourceComparator(pd.DataFrame([entry.to_dict()]))
    result = comparator.compare(pd.DataFrame([east]), pd.DataFrame([official]))
    return result.iloc[0].to_dict()


def test_policy_inference_distinguishes_metric_types() -> None:
    assert infer_comparison_policy("OPERATE_INCOME", "营业收入", "元").method == "numeric"
    assert infer_comparison_policy("BASIC_EPS", "基本每股收益", "元").method == "per_share"
    assert infer_comparison_policy("GROSS_MARGIN", "毛利率", "%").method == "percentage"
    assert infer_comparison_policy("EMPLOYEE_COUNT", "员工人数", "人").method == "integer"
    assert infer_comparison_policy("NOTICE_DATE", "公告日期", "").method == "date"
    assert infer_comparison_policy("DIRECTORS", "董事名单", "").method == "set"


def test_monetary_comparison_uses_normalized_units_and_relative_tolerance() -> None:
    entry = _registry_entry("OPERATE_INCOME", "营业收入", "亿元")
    result = _compare(
        entry,
        _eastmoney_row("OPERATE_INCOME", "营业收入", value_num=10.0, unit="亿元"),
        _official_row(
            "OPERATE_INCOME",
            "营业收入",
            value_num=1_000_000_000.05,
            unit="元",
            tolerance=0.01,
        ),
    )
    assert result["status"] == "WITHIN_ROUNDING"
    assert result["comparison_method"] == "numeric"
    assert result["root_cause"] == "WITHIN_CONFIGURED_TOLERANCE"


def test_percentage_and_per_share_use_metric_specific_tolerance() -> None:
    percent_entry = _registry_entry("GROSS_MARGIN", "毛利率", "%")
    percent = _compare(
        percent_entry,
        _eastmoney_row("GROSS_MARGIN", "毛利率", value_num=12.34, unit="%"),
        _official_row("GROSS_MARGIN", "毛利率", value_num=12.345, unit="%"),
    )
    assert percent["status"] == "WITHIN_ROUNDING"
    assert percent["absolute_tolerance"] == 0.01

    eps_entry = _registry_entry("BASIC_EPS", "基本每股收益", "元")
    eps = _compare(
        eps_entry,
        _eastmoney_row("BASIC_EPS", "基本每股收益", value_num=1.2345, unit="元"),
        _official_row("BASIC_EPS", "基本每股收益", value_num=1.23455, unit="元"),
    )
    assert eps["status"] == "WITHIN_ROUNDING"
    assert eps["absolute_tolerance"] == 0.0001


def test_date_and_set_comparisons_use_normalized_semantics() -> None:
    date_entry = _registry_entry("NOTICE_DATE", "公告日期")
    date_result = _compare(
        date_entry,
        _eastmoney_row("NOTICE_DATE", "公告日期", value_text="2026-03-20 18:00:00"),
        _official_row("NOTICE_DATE", "公告日期", value_text="2026-03-20"),
    )
    assert date_result["status"] == "TEXT_MATCH_NORMALIZED"
    assert date_result["comparison_method"] == "date"

    set_entry = _registry_entry("DIRECTORS", "董事名单")
    set_result = _compare(
        set_entry,
        _eastmoney_row("DIRECTORS", "董事名单", value_text="张三, 李四"),
        _official_row("DIRECTORS", "董事名单", value_text="李四、张三"),
    )
    assert set_result["status"] == "SET_MATCH"
    assert set_result["comparison_method"] == "set"


def test_summary_separates_coverage_from_accuracy() -> None:
    frame = pd.DataFrame(
        [
            {
                "status": "EXACT_MATCH",
                "root_cause": "VALUE_MATCH",
                "source_document": "report.pdf",
                "source_url": "https://example.invalid/report.pdf",
                "source_page": 1,
                "source_row": "营业收入",
            },
            {
                "status": "WITHIN_ROUNDING",
                "root_cause": "WITHIN_CONFIGURED_TOLERANCE",
                "source_document": "report.pdf",
                "source_url": "https://example.invalid/report.pdf",
                "source_page": 1,
                "source_row": "净利润",
            },
            {
                "status": "MISSING_OFFICIAL",
                "root_cause": "OFFICIAL_VALUE_NOT_EXTRACTED",
                "source_document": "",
                "source_url": "",
                "source_page": None,
                "source_row": "",
            },
            {
                "status": "OFFICIAL_PERIOD_NOT_LOADED",
                "root_cause": "REPORT_PERIOD_NOT_LOADED",
                "source_document": "",
                "source_url": "",
                "source_page": None,
                "source_row": "",
            },
        ]
    )
    summary = CrossSourceComparator.summary(frame)
    assert summary["comparison_accuracy"] == 1.0
    assert summary["comparison_coverage"] == 2 / 3
    assert summary["target_extraction_coverage"] == 2 / 3
    assert summary["unresolved_rate"] == 1 / 3
    assert summary["comparable_match_rate"] == 1.0
    assert summary["comparable_match_rate_deprecated"] is True
