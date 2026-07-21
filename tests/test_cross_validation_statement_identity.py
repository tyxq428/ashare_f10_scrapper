from __future__ import annotations

import duckdb
import pandas as pd

from ashare_f10.cross_validation.adapters import load_eastmoney_facts
from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.models import RegistryEntry
from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.models import TargetField


def test_parser_keeps_same_key_separate_by_statement() -> None:
    targets = (
        TargetField(
            "OTHER_COMPRE_INCOME",
            "其他综合收益",
            "balance_sheet",
            ("其他综合收益",),
            ("OTHER_COMPRE_INCOME",),
            ("RPT_F10_FINANCE_GBALANCE",),
            "point_in_time",
        ),
        TargetField(
            "OTHER_COMPRE_INCOME",
            "其他综合收益",
            "income_statement",
            ("其他综合收益",),
            ("OTHER_COMPRE_INCOME",),
            ("RPT_F10_FINANCE_GINCOME",),
        ),
    )
    parser = PdfStatementParser(targets)
    assert len(parser.targets) == 2
    income = next(target for target in parser.targets if target.statement_type == "income_statement")
    assert "其他综合收益的税后净额" in income.aliases
    cashflow = PdfStatementParser(
        (
            TargetField(
                "FINANCE_EXPENSE",
                "财务费用",
                "cash_flow",
                ("财务费用",),
                ("FINANCE_EXPENSE",),
                ("RPT_F10_FINANCE_GCASHFLOW",),
            ),
        )
    ).targets[0]
    assert "财务费用（收益以“－”号填列）" in cashflow.aliases


def test_treasury_shares_is_a_monetary_balance_sheet_item(tmp_path) -> None:
    database = tmp_path / "facts.duckdb"
    frame = pd.DataFrame(
        [
            {
                "security_code": "688521",
                "theme": "财务报表与指标",
                "family": "RPT_F10_FINANCE_GBALANCE",
                "dataset": "资产负债表",
                "record_key": "688521|2025-12-31",
                "report_date": "2025-12-31",
                "event_date": "2025-12-31",
                "period_type": "FY",
                "data_semantics": "point_in_time",
                "field_key": "TREASURY_SHARES",
                "field_name_cn": "库存股",
                "field_category": "PAGE_DISPLAY_FIELD",
                "value_text": "24836121.01",
                "value_num": 24836121.01,
                "unit": "股",
                "source_url": "",
                "source_status": "FACT_DIRECT",
            }
        ]
    )
    connection = duckdb.connect(str(database))
    connection.register("input_frame", frame)
    connection.execute("CREATE TABLE facts AS SELECT * FROM input_frame")
    connection.close()
    result = load_eastmoney_facts(database)
    assert result.iloc[0]["unit"] == "元"
    assert result.iloc[0]["normalized_unit"] == "元"


def test_primary_statement_does_not_fallback_across_statement_types() -> None:
    official_index = {
        (
            "688521",
            "2025-12-31",
            "FY",
            "income_statement",
            "FINANCE_EXPENSE",
        ): [
            {
                "security_code": "688521",
                "report_date": "2025-12-31",
                "period_type": "FY",
                "statement_type": "income_statement",
                "scope": "consolidated",
                "field_key": "FINANCE_EXPENSE",
                "value_num": 52_927_208.41,
            }
        ]
    }
    eastmoney = {
        "security_code": "688521",
        "report_date": "2025-12-31",
        "period_type": "FY",
        "family": "RPT_F10_FINANCE_GCASHFLOW",
        "field_key": "FINANCE_EXPENSE",
    }
    entry = RegistryEntry(
        theme="财务报表与指标",
        family="RPT_F10_FINANCE_GCASHFLOW",
        dataset="现金流量表",
        field_key="FINANCE_EXPENSE",
        field_name_cn="财务费用",
        validation_mode="OFFICIAL_DIRECT",
        statement_type="cash_flow",
        scope="consolidated",
    )
    row, diagnostic = CrossSourceComparator._find_official(official_index, eastmoney, entry)
    assert row is None
    assert diagnostic is None
