from __future__ import annotations

import pandas as pd

from ashare_f10.ascope_bridge.finance import IndustryTemplate, build_financial_tables


def fact(
    report_date: str,
    field_key: str,
    value: float | str,
    available_at: str | None,
    *,
    security_code: str = "000002",
    priority: int = 60,
    record_key: str = "",
    period_basis: str = "CUMULATIVE",
) -> dict:
    return {
        "security_code": security_code,
        "family": "RPT_F10_FINANCE",
        "record_key": record_key or f"{report_date}|{field_key}|{available_at}",
        "report_date": report_date,
        "field_key": field_key,
        "value_num": value if isinstance(value, (int, float)) else None,
        "value_text": value if isinstance(value, str) else str(value),
        "unit": "元" if isinstance(value, (int, float)) else "",
        "source_url": "https://example.invalid/fact",
        "source_status": "FACT_DIRECT",
        "source_priority": priority,
        "available_at": available_at,
        "period_basis": period_basis,
    }


def industrial_facts() -> pd.DataFrame:
    rows = []
    periods = {
        "2025-03-31": (100.0, 60.0, 12.0, 30.0, "2025-04-20"),
        "2025-06-30": (230.0, 135.0, 29.0, 35.0, "2025-08-20"),
        "2025-09-30": (360.0, 210.0, 48.0, 38.0, "2025-10-25"),
        "2025-12-31": (500.0, 300.0, 72.0, 40.0, "2026-03-30"),
    }
    for report_date, (revenue, cost, profit, receivable, available_at) in periods.items():
        rows.extend(
            [
                fact(report_date, "OPERATE_INCOME", revenue, available_at),
                fact(report_date, "OPERATE_COST", cost, available_at),
                fact(report_date, "DEDUCT_PARENT_NETPROFIT", profit, available_at),
                fact(report_date, "ACCOUNTS_RECE", receivable, available_at),
                fact(report_date, "INVENTORY", receivable / 2, available_at),
                fact(report_date, "CONTRACT_LIAB", 5.0, available_at),
                fact(report_date, "NETCASH_OPERATE", revenue / 10, available_at),
                fact(report_date, "CONSTRUCT_LONG_ASSET", revenue / 20, available_at),
                fact(report_date, "SHORT_LOAN", 20.0, available_at),
                fact(report_date, "LONG_LOAN", 10.0, available_at),
                fact(report_date, "TOTAL_EQUITY", 200.0, available_at),
                fact(report_date, "TOTAL_ASSETS", 600.0, available_at),
                fact(report_date, "MONETARYFUNDS", 80.0, available_at),
            ]
        )
    rows.append(
        fact(
            "2025-06-30",
            "OPERATE_INCOME",
            999.0,
            "2026-08-10",
            priority=100,
            record_key="future-revision",
        )
    )
    return pd.DataFrame(rows)


def test_industrial_quarters_are_standalone_and_points_are_not_differenced() -> None:
    result = build_financial_tables(
        industrial_facts(),
        security_id="SZSE.000002",
        security_code="000002",
        industry_template=IndustryTemplate.INDUSTRIAL,
        as_of_date="2026-07-30",
    )
    q2 = result.quarterly[result.quarterly["report_period"] == "2025-06-30"].iloc[0]
    q4 = result.quarterly[result.quarterly["report_period"] == "2025-12-31"].iloc[0]
    assert q2["revenue"] == 130.0
    assert q2["gross_profit"] == 55.0
    assert q2["deducted_net_profit"] == 17.0
    assert q2["accounts_receivable"] == 35.0
    assert q2["interest_bearing_debt"] == 30.0
    assert q4["revenue"] == 140.0
    assert result.annual.iloc[0]["revenue"] == 500.0
    assert len(result.future_rows) == 1


def test_bank_fields_are_not_applicable_instead_of_zero() -> None:
    facts = pd.DataFrame(
        [
            fact(
                "2025-12-31",
                "TOTAL_OPERATE_INCOME",
                1000.0,
                "2026-03-20",
                security_code="000001",
            ),
            fact(
                "2025-12-31",
                "DEDUCT_PARENT_NETPROFIT",
                200.0,
                "2026-03-20",
                security_code="000001",
            ),
            fact(
                "2025-12-31",
                "TOTAL_EQUITY",
                800.0,
                "2026-03-20",
                security_code="000001",
            ),
            fact(
                "2025-12-31",
                "TOTAL_ASSETS",
                10000.0,
                "2026-03-20",
                security_code="000001",
            ),
        ]
    )
    result = build_financial_tables(
        facts,
        security_id="SZSE.000001",
        security_code="000001",
        industry_template=IndustryTemplate.BANK,
        as_of_date="2026-07-30",
    )
    annual = result.annual.iloc[0]
    assert annual["revenue"] == 1000.0
    assert pd.isna(annual["gross_profit"])
    assert pd.isna(annual["inventory"])
    statuses = result.field_status.set_index("field_name")["status"].to_dict()
    assert statuses["gross_profit"] == "NOT_APPLICABLE"
    assert statuses["inventory"] == "NOT_APPLICABLE"
    assert statuses["interest_bearing_debt"] == "NOT_APPLICABLE"


def test_unknown_availability_is_excluded_and_report_date_is_not_used() -> None:
    facts = pd.DataFrame([fact("2025-12-31", "OPERATE_INCOME", 100.0, None)])
    result = build_financial_tables(
        facts,
        security_id="SZSE.000002",
        security_code="000002",
        industry_template=IndustryTemplate.INDUSTRIAL,
        as_of_date="2026-07-30",
    )
    assert result.annual.empty
    assert result.quarterly.empty
    assert result.data_gaps.iloc[0]["status"] == "SOURCE_MISSING"


def test_disclosure_metadata_supplies_available_at_without_changing_report_date() -> None:
    facts = pd.DataFrame([fact("2025-12-31", "OPERATE_INCOME", 100.0, None)])
    disclosures = pd.DataFrame(
        [
            {
                "security_code": "000002",
                "report_date": "2025-12-31",
                "available_at": "2026-03-30",
            }
        ]
    )
    result = build_financial_tables(
        facts,
        security_id="SZSE.000002",
        security_code="000002",
        industry_template=IndustryTemplate.INDUSTRIAL,
        as_of_date="2026-07-30",
        disclosure_dates=disclosures,
    )
    assert result.annual.iloc[0]["available_at"] == "2026-03-30"


def test_equal_priority_conflict_is_quarantined() -> None:
    facts = pd.DataFrame(
        [
            fact("2025-12-31", "OPERATE_INCOME", 100.0, "2026-03-30", record_key="a"),
            fact("2025-12-31", "OPERATE_INCOME", 120.0, "2026-03-30", record_key="b"),
        ]
    )
    result = build_financial_tables(
        facts,
        security_id="SZSE.000002",
        security_code="000002",
        industry_template=IndustryTemplate.INDUSTRIAL,
        as_of_date="2026-07-30",
    )
    assert pd.isna(result.annual.iloc[0]["revenue"])
    status = result.field_status[result.field_status["field_name"] == "revenue"].iloc[0]
    assert status["status"] == "CONFLICTING"
    assert len(result.duplicate_resolution) == 1


def test_direct_standalone_quarter_overrides_cumulative_derivation() -> None:
    facts = industrial_facts()
    direct = pd.DataFrame(
        [
            fact(
                "2025-06-30",
                "OPERATE_INCOME",
                140.0,
                "2025-08-20",
                record_key="direct-q2",
                period_basis="STANDALONE",
            )
        ]
    )
    result = build_financial_tables(
        pd.concat([facts, direct], ignore_index=True),
        security_id="SZSE.000002",
        security_code="000002",
        industry_template=IndustryTemplate.INDUSTRIAL,
        as_of_date="2026-07-30",
    )
    q2 = result.quarterly[result.quarterly["report_period"] == "2025-06-30"].iloc[0]
    assert q2["revenue"] == 140.0
    status = result.field_status[
        (result.field_status["report_period"] == "2025-06-30")
        & (result.field_status["field_name"] == "revenue")
    ].iloc[0]
    assert status["status"] == "SOURCE_DIRECT"
    assert status["derivation_method"] == "direct standalone-quarter source"
