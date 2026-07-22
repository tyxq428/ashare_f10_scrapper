from __future__ import annotations

from pathlib import Path

import duckdb

from ashare_f10.validation.documents.pdf_parser import (
    _choose_amounts,
    _numeric_candidates,
    _parse_number,
    _section_from_text,
)
from ashare_f10.validation.models import OfficialDocument, OfficialFact
from ashare_f10.validation.reconcile.engine import (
    build_logic_checks,
    build_ttm_checks,
    reconcile_official_facts,
)
from ashare_f10.validation.sources.sse import SSEOfficialSource


def test_sse_report_discovery_prefers_corrected_version(monkeypatch) -> None:
    payload = {
        "pageHelp": {
            "data": [
                {
                    "BULLETIN_HEADING": "芯原股份2025年年度报告",
                    "URL": "/disclosure/annual-original.pdf",
                    "SSEDATE": "2026-03-20",
                },
                {
                    "BULLETIN_HEADING": "芯原股份2025年年度报告（修订版）",
                    "URL": "/disclosure/annual-corrected.pdf",
                    "SSEDATE": "2026-04-01",
                },
                {
                    "BULLETIN_HEADING": "芯原股份2025年年度报告摘要",
                    "URL": "/disclosure/annual-summary.pdf",
                    "SSEDATE": "2026-03-20",
                },
                {
                    "BULLETIN_HEADING": "芯原股份2026年第一季度报告",
                    "URL": "/disclosure/q1.pdf",
                    "SSEDATE": "2026-04-28",
                },
            ]
        }
    }
    source = SSEOfficialSource()
    monkeypatch.setattr(source, "_get_json", lambda _params: payload)
    selected = source.select_reports(
        "688521", ["2025-12-31", "2026-03-31"], begin_date="2026-01-01", end_date="2026-12-31"
    )
    assert len(selected) == 2
    annual = next(item for item in selected if item.report_kind == "annual")
    assert annual.version_label == "corrected"
    assert annual.url.endswith("annual-corrected.pdf")


def test_pdf_number_parsing_and_section_detection() -> None:
    assert _parse_number("(1,234.50)") == (-1234.5, 2)
    values = _numeric_candidates(["七、12", "1,234,567.89", "1,000,000.00"])
    current, previous = _choose_amounts(values) or (None, None)
    assert current is not None and current[0] == 1234567.89
    assert previous is not None and previous[0] == 1000000.0
    assert _section_from_text("合并资产负债表\n单位：元") == ("balance_sheet", "consolidated")
    assert _section_from_text("母公司利润表") == ("income_statement", "parent")


def _official_fact(source_row: str, value: float) -> OfficialFact:
    return OfficialFact(
        "688521",
        "2025-12-31",
        "balance_sheet",
        "consolidated",
        "DEFER_TAX_ASSET",
        "递延所得税资产",
        value,
        "元",
        "元",
        "芯原股份2025年年度报告",
        "https://example.invalid/report.pdf",
        88,
        source_row,
        "PDF_TABLE",
        1.0,
        "high",
    )


def test_note_reference_without_amount_is_quarantined() -> None:
    fact = _official_fact("递延所得税资产 七、29", 29.0)
    assert fact.source_status == "PARSE_SUSPECT"
    assert fact.confidence == "low"
    assert fact.quality_flags == ("NOTE_REFERENCE_AS_AMOUNT",)
    assert not fact.usable_for_reconciliation
    assert fact.raw_value == 29.0


def test_note_reference_with_real_amount_is_not_quarantined() -> None:
    fact = _official_fact("递延所得税资产 七、29 1,234,567.89 1,000,000.00", 1234567.89)
    assert fact.source_status == "FACT_DIRECT"
    assert fact.quality_flags == ()
    assert fact.usable_for_reconciliation


def _build_fact_db(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute(
        "CREATE TABLE facts (security_code VARCHAR, report_date VARCHAR, family VARCHAR, field_key VARCHAR, field_name_cn VARCHAR, value_num DOUBLE, unit VARCHAR)"
    )
    rows = [
        ("688521", "2025-12-31", "RPT_F10_FINANCE_GBALANCE", "TOTAL_ASSETS", "资产总计", 1000.0, "元"),
        ("688521", "2025-12-31", "RPT_F10_FINANCE_GBALANCE", "TOTAL_LIABILITIES", "负债合计", 600.0, "元"),
        ("688521", "2025-12-31", "RPT_F10_FINANCE_GBALANCE", "TOTAL_EQUITY", "所有者权益合计", 400.0, "元"),
        (
            "688521",
            "2025-12-31",
            "RPT_F10_FINANCE_GBALANCE",
            "TOTAL_LIAB_EQUITY",
            "负债和所有者权益总计",
            1000.0,
            "元",
        ),
    ]
    for report_date, value in (
        ("2025-06-30", 20.0),
        ("2025-09-30", 30.0),
        ("2025-12-31", 40.0),
        ("2026-03-31", 10.0),
    ):
        rows.append(
            ("688521", report_date, "RPT_F10_FINANCE_GINCOMEQC", "OPERATE_INCOME", "营业收入", value, "元")
        )
        rows.append(
            (
                "688521",
                report_date,
                "RPT_F10_FINANCE_GINCOMEQC",
                "PARENT_NETPROFIT",
                "归母净利润",
                value / 10,
                "元",
            )
        )
    rows.extend(
        [
            ("688521", "2025-12-31", "RPT_F10_FINANCE_GINCOME", "OPERATE_INCOME", "营业收入", 100.0, "元"),
            ("688521", "2025-03-31", "RPT_F10_FINANCE_GINCOME", "OPERATE_INCOME", "营业收入", 10.0, "元"),
            ("688521", "2026-03-31", "RPT_F10_FINANCE_GINCOME", "OPERATE_INCOME", "营业收入", 10.0, "元"),
            ("688521", "2025-12-31", "RPT_F10_FINANCE_GINCOME", "PARENT_NETPROFIT", "归母净利润", 10.0, "元"),
            ("688521", "2025-03-31", "RPT_F10_FINANCE_GINCOME", "PARENT_NETPROFIT", "归母净利润", 1.0, "元"),
            ("688521", "2026-03-31", "RPT_F10_FINANCE_GINCOME", "PARENT_NETPROFIT", "归母净利润", 1.0, "元"),
        ]
    )
    connection.executemany("INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    connection.close()


def test_reconciliation_logic_and_ttm(tmp_path: Path) -> None:
    db_path = tmp_path / "facts.duckdb"
    _build_fact_db(db_path)
    document = OfficialDocument(
        "SSE",
        "688521",
        "2025年年度报告",
        "2026-03-20",
        "2025-12-31",
        "annual",
        "original",
        "https://example.invalid/report.pdf",
    )
    official = [
        OfficialFact(
            "688521",
            "2025-12-31",
            "balance_sheet",
            "consolidated",
            key,
            name,
            value,
            "元",
            "元",
            document.title,
            document.url,
            1,
            name,
            "TEST",
            1.0,
            "high",
        )
        for key, name, value in (
            ("TOTAL_ASSETS", "资产总计", 1000.0),
            ("TOTAL_LIABILITIES", "负债合计", 600.0),
            ("TOTAL_EQUITY", "所有者权益合计", 400.0),
            ("TOTAL_LIAB_EQUITY", "负债和所有者权益总计", 1000.0),
        )
    ]
    official.append(_official_fact("递延所得税资产 七、29", 29.0))
    reconciled = reconcile_official_facts(db_path, official)
    balance_results = [item for item in reconciled if item.statement_type == "balance_sheet"]
    assert all(item.status == "EXACT_MATCH" for item in balance_results)
    assert all(item.field_key != "DEFER_TAX_ASSET" for item in reconciled)
    assert [item.status for item in build_logic_checks(official)[:2]] == ["PASS", "PASS"]
    ttm = build_ttm_checks(db_path, "688521", "2026-03-31")
    assert all(item.status == "PASS" for item in ttm)
    assert ttm[0].independent_quarters_value == 100.0
    assert ttm[0].cumulative_formula_value == 100.0
