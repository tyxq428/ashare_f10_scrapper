from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

import ashare_f10.api.app as app_module

COLUMNS = """
security_code VARCHAR, theme VARCHAR, family VARCHAR, dataset VARCHAR,
record_key VARCHAR, report_date VARCHAR, event_date VARCHAR, period_type VARCHAR,
data_semantics VARCHAR, field_key VARCHAR, field_name_cn VARCHAR,
field_category VARCHAR, value_text VARCHAR, value_num DOUBLE, unit VARCHAR,
source_url VARCHAR, source_status VARCHAR
"""


def make_db(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute(f"CREATE TABLE facts ({COLUMNS})")
    rows = [
        ["688521", "财务", "CASH", "财务/CASH", "1", "2026-03-31", None, "Q1", "flow", "CASH_A", "现金项目A", "PAGE_DISPLAY_FIELD", "100", 100.0, "元", "", "FACT_DIRECT"],
        ["688521", "财务", "CASH", "财务/CASH", "2", "2025-12-31", None, "FY", "flow", "CASH_B", "现金项目B同比", "PAGE_DISPLAY_FIELD", "200", 200.0, "元", "", "FACT_DIRECT"],
        ["688521", "财务", "INCOME", "财务/INCOME", "3", "2025-12-31", None, "FY", "flow", "REVENUE", "营业收入", "PAGE_DISPLAY_FIELD", "300", 300.0, "元", "", "FACT_DIRECT"],
    ]
    connection.executemany("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    connection.close()


def test_structured_search_facets_and_export(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "api.duckdb"
    make_db(db_path)
    monkeypatch.setattr(app_module, "latest_paths", lambda _code: ({"artifacts": {}}, db_path))
    client = TestClient(app_module.app)

    query = {
        "base_query": "现金",
        "base_match_type": "contains",
        "search_steps": [
            {
                "query": "同比",
                "operation": "exclude",
                "match_type": "contains",
                "columns": ["field_name_cn"],
                "threshold": 60,
                "enabled": True,
            }
        ],
        "filters": [],
        "sort": [{"column": "report_date", "direction": "desc"}],
        "page": 1,
        "page_size": 100,
    }
    response = client.post("/api/stocks/688521/search/query", json=query)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["field_key"] == "CASH_A"

    response = client.post(
        "/api/stocks/688521/search/facets",
        json={"query": query, "column": "family", "term": "", "limit": 20},
    )
    assert response.status_code == 200, response.text
    assert response.json()["values"] == [{"value": "CASH", "count": 1}]

    response = client.post(
        "/api/stocks/688521/search/export",
        json={"query": query, "format": "csv", "max_rows": 100},
    )
    assert response.status_code == 200
    assert "CASH_A" in response.content.decode("utf-8-sig")
