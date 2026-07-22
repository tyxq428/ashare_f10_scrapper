from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.derived import derive_independent_quarters
from ashare_f10.validation.documents.pdf_parser import (
    _bounded_alias_value_segment,
    _canonical_value,
)


def test_sse_finance_expense_preserves_reported_sign() -> None:
    assert _canonical_value("FINANCE_EXPENSE", -744126.44, "SSE") == -744126.44
    assert _canonical_value("FINANCE_EXPENSE", -744126.44, "CNINFO") == 744126.44


def test_blank_asset_disposal_row_cannot_borrow_operating_profit() -> None:
    context = (
        "资产处置收益（损失以‘－’号填列） 三、营业利润（亏损以‘－’号填列） -42,379,273.29 -58,877,172.26"
    )
    segment, bounded = _bounded_alias_value_segment(
        context,
        "资产处置收益",
        ["资产处置收益", "营业利润"],
    )
    assert bounded is True
    assert "42,379,273.29" not in segment


def test_non_additive_cash_balances_are_not_quarter_differenced() -> None:
    columns = [
        "security_code",
        "report_date",
        "period_type",
        "statement_type",
        "scope",
        "field_key",
        "value_num",
        "value_text",
        "source_status",
        "source_row",
        "record_key",
    ]
    frame = pd.DataFrame(
        [
            [
                "688521",
                "2022-03-31",
                "Q1",
                "cash_flow",
                "consolidated",
                "BEGIN_CCE",
                921.0,
                "921",
                "FACT_DIRECT",
                "Q1",
                "q1-begin",
            ],
            [
                "688521",
                "2022-06-30",
                "H1",
                "cash_flow",
                "consolidated",
                "BEGIN_CCE",
                921.0,
                "921",
                "FACT_DIRECT",
                "H1",
                "h1-begin",
            ],
            [
                "688521",
                "2022-03-31",
                "Q1",
                "cash_flow",
                "consolidated",
                "NETCASH_OPERATE",
                10.0,
                "10",
                "FACT_DIRECT",
                "Q1",
                "q1-flow",
            ],
            [
                "688521",
                "2022-06-30",
                "H1",
                "cash_flow",
                "consolidated",
                "NETCASH_OPERATE",
                25.0,
                "25",
                "FACT_DIRECT",
                "H1",
                "h1-flow",
            ],
        ],
        columns=columns,
    )
    result = derive_independent_quarters(frame)
    assert set(result["field_key"]) == {"NETCASH_OPERATE"}
    assert result.iloc[0]["value_num"] == 15.0
