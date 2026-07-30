from __future__ import annotations

from ashare_f10.normalize.facts import iter_facts


def test_financial_record_preserves_notice_date_as_available_at() -> None:
    combined = {
        "metadata": {"security": {"code": "000001"}},
        "groups": [
            {
                "theme": "财务分析",
                "family": "RPT_F10_FINANCE_GINCOME",
                "records": [
                    {
                        "SECURITY_CODE": "000001",
                        "REPORT_DATE": "2026-03-31 00:00:00",
                        "NOTICE_DATE": "2026-04-25 00:00:00",
                        "UPDATE_DATE": "2026-04-26 00:00:00",
                        "OPERATE_INCOME": 100.0,
                    }
                ],
                "requests": [
                    {"request": {"url": "https://example.invalid/finance"}}
                ],
            }
        ],
    }

    facts = list(iter_facts(combined))
    income = next(item for item in facts if item["field_key"] == "OPERATE_INCOME")
    assert income["report_date"] == "2026-03-31"
    assert income["available_at"] == "2026-04-25"


def test_report_date_is_not_used_as_availability() -> None:
    combined = {
        "metadata": {"security": {"code": "000002"}},
        "groups": [
            {
                "theme": "财务分析",
                "family": "RPT_F10_FINANCE_GINCOME",
                "records": [
                    {
                        "SECURITY_CODE": "000002",
                        "REPORT_DATE": "2025-12-31 00:00:00",
                        "OPERATE_INCOME": 200.0,
                    }
                ],
                "requests": [],
            }
        ],
    }

    income = next(
        item for item in iter_facts(combined) if item["field_key"] == "OPERATE_INCOME"
    )
    assert income["report_date"] == "2025-12-31"
    assert income["available_at"] is None
