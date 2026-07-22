from __future__ import annotations

from ashare_f10.validation.documents.pdf_parser import financial_scope_from_texts


def test_old_quarter_report_is_classified_as_summary_only() -> None:
    assert (
        financial_scope_from_texts(
            ["二、公司主要财务数据和股东变化\n2.1 主要财务数据\n总资产 3,145,094,219.81"]
        )
        == "SUMMARY_ONLY"
    )


def test_full_statement_heading_takes_priority() -> None:
    assert (
        financial_scope_from_texts(
            [
                "二、公司主要财务数据",
                "合并资产负债表\n单位：元",
            ]
        )
        == "FULL_STATEMENTS"
    )
