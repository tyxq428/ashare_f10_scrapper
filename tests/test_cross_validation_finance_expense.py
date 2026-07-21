from __future__ import annotations

from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.models import RegistryEntry
from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.models import TargetField


def test_cashflow_finance_expense_has_exact_supplement_alias() -> None:
    target = TargetField(
        "FINANCE_EXPENSE",
        "财务费用",
        "cash_flow",
        ("财务费用",),
        ("FINANCE_EXPENSE",),
        ("RPT_F10_FINANCE_GCASHFLOW",),
    )
    parsed = PdfStatementParser((target,)).targets[0]
    assert parsed.aliases[0] == "财务费用（收益以“－”号填列）"


def test_derived_finance_expense_prefers_income_statement() -> None:
    official_index = {
        ("688521", "2025-12-31", "FY", "cash_flow", "FINANCE_EXPENSE"): [
            {
                "statement_type": "cash_flow",
                "scope": "consolidated",
                "value_num": 50_084_519.03,
            }
        ],
        ("688521", "2025-12-31", "FY", "income_statement", "FINANCE_EXPENSE"): [
            {
                "statement_type": "income_statement",
                "scope": "consolidated",
                "value_num": 52_927_208.41,
            }
        ],
    }
    eastmoney = {
        "security_code": "688521",
        "report_date": "2025-12-31",
        "period_type": "FY",
        "family": "RPT_F10_FINANCE_GRATIO",
        "field_key": "FINANCE_EXPENSE",
    }
    entry = RegistryEntry(
        theme="财务报表与指标",
        family="RPT_F10_FINANCE_GRATIO",
        dataset="财务比率",
        field_key="FINANCE_EXPENSE",
        field_name_cn="财务费用",
        validation_mode="OFFICIAL_DERIVED",
        statement_type="financial_ratio",
        scope="consolidated",
    )
    row, diagnostic = CrossSourceComparator._find_official(official_index, eastmoney, entry)
    assert diagnostic is None
    assert row is not None
    assert row["statement_type"] == "income_statement"
    assert row["value_num"] == 52_927_208.41
