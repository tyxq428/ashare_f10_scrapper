from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
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


def _fact(field_key: str, label: str, statement_type: str, text: str):
    target = TargetField(
        field_key,
        label,
        statement_type,
        (label,),
        (field_key,),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    )
    return PdfStatementParser((target,))._extract_from_text(
        text,
        target,
        _document(),
        1,
        ("千元", 1000.0),
        "consolidated",
    )


def test_note_column_after_label_does_not_block_preceding_value() -> None:
    fact = _fact(
        "INVEST_PAY_CASH",
        "投资支付的现金",
        "cash_flow",
        "(56)(d) (1,630,616) (129,979) – (3,000,000)\n投资支付的现金 四\n"
        "(56)(f) (28,251) (696,654) – –\n取得子公司支付的现金净额 四",
    )
    assert fact is not None
    assert fact.value == 1_630_616_000


def test_nonbusiness_rows_use_preceding_values() -> None:
    income = _fact(
        "NONBUSINESS_INCOME",
        "营业外收入",
        "income_statement",
        "(52)(a) 386,539 311,972 – –\n加：营业外收入 四\n(52)(b) (232,129) (373,060) – –\n减：营业外支出 四",
    )
    expense = _fact(
        "NONBUSINESS_EXPENSE",
        "营业外支出",
        "income_statement",
        "(52)(a) 386,539 311,972 – –\n加：营业外收入 四\n"
        "(52)(b) (232,129) (373,060) – –\n减：营业外支出 四\n"
        "14,917,877 13,607,261 2,485,980 5,042,321\n三、利润总额",
    )
    assert income is not None and income.value == 386_539_000
    assert expense is not None and expense.value == 232_129_000
