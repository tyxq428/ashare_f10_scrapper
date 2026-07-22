from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from ashare_f10.api.search import export_search_rows, facet_facts, query_facts
from ashare_f10.models import SearchColumnFilter, SearchQueryRequest, SearchSort, SearchStep

COLUMNS = """
security_code VARCHAR, theme VARCHAR, family VARCHAR, dataset VARCHAR,
record_key VARCHAR, report_date VARCHAR, event_date VARCHAR, period_type VARCHAR,
data_semantics VARCHAR, field_key VARCHAR, field_name_cn VARCHAR,
field_category VARCHAR, value_text VARCHAR, value_num DOUBLE, unit VARCHAR,
source_url VARCHAR, source_status VARCHAR
"""


def insert_fact(
    connection: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    family: str,
    field_key: str,
    field_name: str,
    value: float,
    theme: str = "财务报表与指标",
) -> None:
    connection.execute(
        "INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            "688521",
            theme,
            family,
            f"{theme}/{family}",
            f"{family}|{report_date}|{field_key}",
            report_date,
            report_date,
            "Q",
            "flow",
            field_key,
            field_name,
            "PAGE_DISPLAY_FIELD",
            str(value),
            value,
            "元",
            "https://example.test",
            "FACT_DIRECT",
        ],
    )


@pytest.fixture
def search_db(tmp_path: Path) -> Path:
    path = tmp_path / "search.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(f"CREATE TABLE facts ({COLUMNS})")
    insert_fact(
        connection,
        report_date="2026-03-31",
        family="RPT_F10_FINANCE_GCASHFLOW",
        field_key="CONSTRUCT_LONG_ASSET",
        field_name="购建固定资产、无形资产和其他长期资产支付的现金",
        value=1_929_000_000,
    )
    insert_fact(
        connection,
        report_date="2026-03-31",
        family="RPT_F10_FINANCE_GCASHFLOWQC",
        field_key="CONSTRUCT_LONG_ASSET_YOY",
        field_name="购建固定资产、无形资产和其他长期资产支付的现金同比变化",
        value=380.4225,
    )
    insert_fact(
        connection,
        report_date="2025-12-31",
        family="RPT_F10_FINANCE_GCASHFLOW",
        field_key="NETCASH_OPERATE",
        field_name="经营活动产生的现金流量净额",
        value=900_000_000,
    )
    insert_fact(
        connection,
        report_date="2025-09-30",
        family="RPT_F10_FINANCE_GINCOME",
        field_key="TOTAL_OPERATE_INCOME",
        field_name="营业总收入",
        value=2_100_000_000,
    )
    connection.close()
    return path


def test_chained_include_and_exclude_search(search_db: Path) -> None:
    request = SearchQueryRequest(
        base_query="购建",
        base_match_type="contains",
        search_steps=[
            SearchStep(query="现金", operation="include", match_type="contains"),
            SearchStep(query="同比", operation="exclude", match_type="contains"),
        ],
        page=1,
        page_size=50,
    )
    result = query_facts(search_db, request)
    assert result["total"] == 1
    assert result["rows"][0]["field_key"] == "CONSTRUCT_LONG_ASSET"
    assert [item["count"] for item in result["stage_counts"][-3:]] == [2, 2, 1]


def test_or_search_adds_records_from_filtered_scope(search_db: Path) -> None:
    request = SearchQueryRequest(
        base_query="购建",
        base_match_type="contains",
        search_steps=[SearchStep(query="经营", operation="or", match_type="contains")],
        page=1,
        page_size=50,
    )
    result = query_facts(search_db, request)
    assert result["total"] == 3
    assert {row["field_key"] for row in result["rows"]} == {
        "CONSTRUCT_LONG_ASSET",
        "CONSTRUCT_LONG_ASSET_YOY",
        "NETCASH_OPERATE",
    }


def test_excel_filters_sorting_and_pagination(search_db: Path) -> None:
    request = SearchQueryRequest(
        filters=[
            SearchColumnFilter(
                column="family",
                operator="in",
                values=["RPT_F10_FINANCE_GCASHFLOW", "RPT_F10_FINANCE_GCASHFLOWQC"],
            ),
            SearchColumnFilter(
                column="effective_date",
                operator="between",
                lower="2026-01-01",
                upper="2026-12-31",
            ),
        ],
        sort=[SearchSort(column="value_num", direction="desc")],
        page=1,
        page_size=1,
    )
    first = query_facts(search_db, request)
    assert first["total"] == 2
    assert first["page_count"] == 2
    assert first["rows"][0]["field_key"] == "CONSTRUCT_LONG_ASSET"

    request.page = 2
    second = query_facts(search_db, request)
    assert second["rows"][0]["field_key"] == "CONSTRUCT_LONG_ASSET_YOY"


def test_facets_respect_other_filters(search_db: Path) -> None:
    request = SearchQueryRequest(
        filters=[
            SearchColumnFilter(column="theme", operator="exact", value="财务报表与指标"),
            SearchColumnFilter(column="family", operator="exact", value="RPT_F10_FINANCE_GCASHFLOW"),
        ]
    )
    facet = facet_facts(search_db, request, "family")
    values = {item["value"]: item["count"] for item in facet["values"]}
    assert values["RPT_F10_FINANCE_GCASHFLOW"] == 2
    assert values["RPT_F10_FINANCE_GCASHFLOWQC"] == 1
    assert values["RPT_F10_FINANCE_GINCOME"] == 1


def test_export_uses_complete_filtered_result(search_db: Path) -> None:
    request = SearchQueryRequest(base_query="现金", base_match_type="contains")
    content, media_type, filename = export_search_rows(search_db, request)
    text = content.decode("utf-8-sig")
    assert media_type.startswith("text/csv")
    assert filename.endswith(".csv")
    assert "CONSTRUCT_LONG_ASSET" in text
    assert "NETCASH_OPERATE" in text


def test_rejects_unknown_columns(search_db: Path) -> None:
    request = SearchQueryRequest(
        filters=[SearchColumnFilter(column="DROP TABLE facts", operator="exact", value="x")]
    )
    with pytest.raises(ValueError, match="不支持的搜索列"):
        query_facts(search_db, request)
