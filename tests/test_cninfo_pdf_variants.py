from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import (
    PdfStatementParser,
    _choose_amounts,
    _heading_events,
    _numeric_candidates,
    _unit_info,
)
from ashare_f10.validation.models import OfficialDocument, TargetField
from ashare_f10.validation.sources.cninfo import _date_text


def test_cninfo_timestamp_uses_china_calendar_date() -> None:
    assert _date_text(1774886400000) == "2026-03-31"


def test_cninfo_financial_heading_and_unit_variants() -> None:
    assert _heading_events(None, "2025年12月31日合并资产负债表（续）")[-1][1:] == (
        "balance_sheet",
        "consolidated",
    )
    assert _heading_events(None, "2025年度合并及公司利润表")[-1][1:] == (
        "income_statement",
        "consolidated",
    )
    assert _heading_events(None, "1、合并现金流量表")[-1][1:] == (
        "cash_flow",
        "consolidated",
    )
    assert _unit_info("除特别注明外，金额单位为人民币千元") == ("千元", 1000.0)
    assert _unit_info("归属于上市公司股东的净利润（千元）") == ("千元", 1000.0)


def test_numeric_candidates_do_not_concatenate_columns_or_use_note_number() -> None:
    values = _numeric_candidates(["四(42) 308,226,647 284,420,059"])
    current, previous = _choose_amounts(values) or (None, None)
    assert current is not None and current[0] == 308_226_647
    assert previous is not None and previous[0] == 284_420_059


def test_text_parser_supports_value_before_label_and_row_unit() -> None:
    target = TargetField(
        "OPERATE_INCOME",
        "营业收入",
        "income_statement",
        ("营业收入",),
        ("OPERATE_INCOME",),
        ("RPT_F10_FINANCE_GINCOME",),
    )
    document = OfficialDocument(
        "CNINFO",
        "002352",
        "2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://example.invalid/annual.pdf",
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        "四(42) 308,226,647 284,420,059\n一、营业收入",
        target,
        document,
        159,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 308_226_647_000


def test_text_parser_supports_split_summary_with_thousand_yuan_unit() -> None:
    target = TargetField(
        "DEDUCT_PARENT_NETPROFIT",
        "扣非归母净利润",
        "summary",
        ("归属于上市公司股东的扣除非经常性损益的净利润",),
        ("DEDUCT_PARENT_NETPROFIT",),
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
        "https://example.invalid/q1.pdf",
    )
    text = "\n".join(
        [
            "归属于上市公司股东的扣除非经常性损益",
            "2,317,341 1,973,620 17.42%",
            "的净利润（千元）",
        ]
    )
    fact = PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        document,
        2,
        ("元", 1.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 2_317_341_000
