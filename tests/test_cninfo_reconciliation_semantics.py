from __future__ import annotations

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.models import RegistryEntry
from ashare_f10.validation.documents.pdf_parser import (
    PdfStatementParser,
    _canonical_value,
    _page_unit_info,
    _row_unit_info,
)
from ashare_f10.validation.models import OfficialDocument, TargetField


def _document() -> OfficialDocument:
    return OfficialDocument(
        "CNINFO",
        "002352",
        "2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://example.invalid/report.pdf",
    )


def test_page_unit_ignores_eps_row_unit_and_row_unit_keeps_it() -> None:
    text = "七、综合收益总额 2,291,538\n基本每股收益（人民币元）0.51"
    assert _page_unit_info(text) is None
    assert _row_unit_info("基本每股收益（人民币元）0.51") == ("元", 1.0)


def test_annual_label_prefers_preceding_value_row() -> None:
    target = TargetField(
        "OPERATE_COST",
        "营业成本",
        "income_statement",
        ("营业成本",),
        ("OPERATE_COST",),
        ("RPT_F10_FINANCE_GINCOME",),
    )
    text = "(42) (267,178,276) (244,809,787) – –\n减：营业成本 四\n(43) (764,777) (714,325)"
    fact = PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        _document(),
        159,
        ("千元", 1000.0),
        "consolidated",
    )
    assert fact is not None
    assert fact.value == 267_178_276_000


def test_income_and_cash_outflow_presentation_signs_are_canonicalized() -> None:
    assert _canonical_value("MANAGE_EXPENSE", -19_499_245) == 19_499_245
    assert _canonical_value("TOTAL_OPERATE_OUTFLOW", -395_565_795) == 395_565_795
    assert _canonical_value("TREASURY_SHARES", -1_542_636) == 1_542_636
    assert _canonical_value("FAIRVALUE_CHANGE_INCOME", -48_996) == -48_996


def test_business_rd_does_not_fallback_to_income_statement() -> None:
    official_index = {
        ("002352", "2025-12-31", "FY", "income_statement", "RESEARCH_EXPENSE"): [
            {
                "statement_type": "income_statement",
                "scope": "consolidated",
                "value_num": 2_169_906_000,
            }
        ]
    }
    eastmoney = {
        "security_code": "002352",
        "report_date": "2025-12-31",
        "period_type": "FY",
        "family": "RPT_F10_BUSINESS_RDEXPENSE",
        "field_key": "RESEARCH_EXPENSE",
    }
    entry = RegistryEntry(
        theme="经营业务与研发",
        family="RPT_F10_BUSINESS_RDEXPENSE",
        dataset="研发投入",
        field_key="RESEARCH_EXPENSE",
        field_name_cn="研发投入",
        validation_mode="OFFICIAL_DOCUMENT_EVENT",
        statement_type="business_review",
        scope="consolidated",
    )
    row, diagnostic = CrossSourceComparator._find_official(official_index, eastmoney, entry)
    assert row is None
    assert diagnostic is None
