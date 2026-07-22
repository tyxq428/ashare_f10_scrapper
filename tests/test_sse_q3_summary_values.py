from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import (
    _numeric_candidates,
    _select_summary_amount,
)
from ashare_f10.validation.models import OfficialDocument, TargetField

MODERN_Q3_HEADER = "本报告期比上年同期增减 年初至报告期末"
LEGACY_Q3_HEADER = (
    "本报告期末 上年度末 本报告期末比上年度末增减 年初至报告期末 上年初至上年报告期末 比上年同期增减"
)


def _document(report_kind: str) -> OfficialDocument:
    return OfficialDocument(
        source="SSE",
        security_code="688521",
        title="测试报告",
        publish_date="2023-10-28",
        report_date="2023-09-30" if report_kind == "q3" else "2023-03-31",
        report_kind=report_kind,
        version_label="original",
        url="https://example.invalid/report.pdf",
    )


def _target(semantics: str = "flow") -> TargetField:
    return TargetField(
        "OPERATE_INCOME",
        "营业收入",
        "income_statement",
        ("营业收入",),
        ("OPERATE_INCOME",),
        ("RPT_F10_FINANCE_GINCOME",),
        semantics,
    )


def test_q3_flow_summary_selects_year_to_date_value() -> None:
    context = "营业收入 671,661,479.01 3.66 1,884,150,580.19 23.87"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text=MODERN_Q3_HEADER,
    )
    assert selected is not None
    assert selected[0] == 1_884_150_580.19


def test_q3_flow_summary_with_unavailable_quarter_columns_uses_first_number() -> None:
    context = "经营活动产生的现金流量净额 不适用 不适用 -306,604,109.75 18.20"
    target = TargetField(
        "NETCASH_OPERATE",
        "经营活动产生的现金流量净额",
        "cash_flow",
        ("经营活动产生的现金流量净额",),
        ("NETCASH_OPERATE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
        "flow",
    )
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        target,
        _document("q3"),
        context,
        page_text=MODERN_Q3_HEADER,
    )
    assert selected is not None
    assert selected[0] == -306_604_109.75


def test_q3_point_in_time_summary_keeps_period_end_value() -> None:
    context = "总资产 4,457,634,651.81 3,858,272,515.48 15.53"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target("point_in_time"),
        _document("q3"),
        context,
        page_text=MODERN_Q3_HEADER,
    )
    assert selected is not None
    assert selected[0] == 4_457_634_651.81


def test_legacy_q3_summary_uses_first_year_to_date_amount() -> None:
    context = "营业收入 1,060,887,323.03 950,580,713.27 11.60"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text=LEGACY_Q3_HEADER,
    )
    assert selected is not None
    assert selected[0] == 1_060_887_323.03


def test_q1_summary_keeps_first_value() -> None:
    context = "营业收入 580,891,974.65 -13.51"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q1"),
        context,
        page_text="第一季度主要财务数据",
    )
    assert selected is not None
    assert selected[0] == 580_891_974.65


def test_modern_q3_with_one_unavailable_change_column_uses_second_amount() -> None:
    context = "营业收入 671,661,479.01 不适用 1,884,150,580.19 23.87"
    selected = _select_summary_amount(
        _numeric_candidates([context]),
        _target(),
        _document("q3"),
        context,
        page_text="交错列标题不影响基于行形状的选择",
    )
    assert selected is not None
    assert selected[0] == 1_884_150_580.19
