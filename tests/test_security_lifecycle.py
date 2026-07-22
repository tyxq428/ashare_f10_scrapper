from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.lifecycle import (
    build_security_lifecycle,
    infer_listing_date_from_eastmoney,
    normalize_date,
)


def test_normalize_date_supports_common_formats() -> None:
    assert normalize_date("2020-08-18") == "2020-08-18"
    assert normalize_date("2020年8月18日") == "2020-08-18"
    assert normalize_date("20200818") == "2020-08-18"
    assert normalize_date("not-a-date") is None


def test_infer_listing_date_uses_explicit_field_only() -> None:
    frame = pd.DataFrame(
        [
            {
                "field_key": "REPORT_DATE",
                "value_text": "2016-12-31",
                "family": "RPT_F10_FINANCE_GBALANCE",
            },
            {
                "field_key": "LISTING_DATE",
                "value_text": "2020-08-18",
                "family": "RPT_F10_BASIC_ORGINFO",
            },
        ]
    )
    value, source = infer_listing_date_from_eastmoney(frame)
    assert value == "2020-08-18"
    assert source == "EASTMONEY:RPT_F10_BASIC_ORGINFO:LISTING_DATE"


def test_688521_pre_listing_periods_are_not_periodic_report_gaps() -> None:
    lifecycle = build_security_lifecycle(
        "688521",
        "SH",
        [
            "2016-12-31",
            "2019-12-31",
            "2020-03-31",
            "2020-06-30",
            "2020-09-30",
            "2020-12-31",
        ],
        "2020-08-18",
        "SSE_COMPANY_PROFILE",
    )
    assert lifecycle.pre_listing_report_dates == [
        "2016-12-31",
        "2019-12-31",
        "2020-03-31",
        "2020-06-30",
    ]
    assert lifecycle.periodic_expected_report_dates == ["2020-09-30", "2020-12-31"]
    assert lifecycle.listing_transition_report_dates == ["2020-09-30"]
    assert lifecycle.period_class("2019-12-31") == "PRE_LISTING_PERIOD"
    assert lifecycle.period_class("2020-09-30") == "LISTING_TRANSITION_PERIOD"
    assert lifecycle.period_class("2020-12-31") == "POST_LISTING_PERIODIC_EXPECTED"
