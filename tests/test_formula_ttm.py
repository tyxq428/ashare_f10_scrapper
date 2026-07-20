from pathlib import Path

import duckdb

from ashare_f10.calculate.formula import evaluate_formula
from ashare_f10.calculate.ttm import compute_ttm

COLUMNS = """
security_code VARCHAR, theme VARCHAR, family VARCHAR, dataset VARCHAR,
record_key VARCHAR, report_date VARCHAR, event_date VARCHAR, period_type VARCHAR,
data_semantics VARCHAR, field_key VARCHAR, field_name_cn VARCHAR,
field_category VARCHAR, value_text VARCHAR, value_num DOUBLE, unit VARCHAR,
source_url VARCHAR, source_status VARCHAR
"""


def insert_fact(con, field, name, period, value, family, semantics="flow", unit="元"):
    con.execute(
        "INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ["688521", "财务", family, family, period, period, None, "Q", semantics, field, name,
         "PAGE_DISPLAY_FIELD", str(value), value, unit, "", "FACT_DIRECT"],
    )


def make_db(path: Path):
    con = duckdb.connect(str(path))
    con.execute(f"CREATE TABLE facts ({COLUMNS})")
    for period, value in [
        ("2025-06-30", 20.0), ("2025-09-30", 30.0),
        ("2025-12-31", 40.0), ("2026-03-31", 10.0),
    ]:
        insert_fact(con, "REVENUE_Q", "单季度收入", period, value, "RPT_F10_FINANCE_GINCOMEQC")
    insert_fact(con, "CIP", "在建工程", "2026-03-31", 25.0, "RPT_F10_FINANCE_GBALANCE", "point_in_time")
    insert_fact(con, "TOTAL_ASSETS", "资产总计", "2026-03-31", 100.0, "RPT_F10_FINANCE_GBALANCE", "point_in_time")
    con.close()


def test_four_quarter_ttm(tmp_path):
    db = tmp_path / "test.duckdb"
    make_db(db)
    result = compute_ttm(db, "REVENUE_Q", "2026-03-31")
    assert result.value == 100.0
    assert result.method == "FOUR_INDEPENDENT_QUARTERS"
    assert len(result.components) == 4


def test_formula_fields_and_chinese_names(tmp_path):
    db = tmp_path / "test.duckdb"
    make_db(db)
    result = evaluate_formula(db, 'F("在建工程") / F("资产总计")', "2026-03-31")
    assert result["value"] == 0.25
    assert len(result["trace"]) == 2
