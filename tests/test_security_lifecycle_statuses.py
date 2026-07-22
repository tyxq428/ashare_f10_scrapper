from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.lifecycle import apply_lifecycle_statuses, lifecycle_period_frame


def test_lifecycle_statuses_separate_prelisting_and_parser_gaps() -> None:
    comparison = pd.DataFrame(
        [
            {
                "report_date": "2019-12-31",
                "status": "OFFICIAL_PERIOD_NOT_LOADED",
                "verification_grade": "E",
                "notes": "",
            },
            {
                "report_date": "2020-09-30",
                "status": "MISSING_OFFICIAL",
                "verification_grade": "E",
                "notes": "",
            },
            {
                "report_date": "2021-06-30",
                "status": "OFFICIAL_PERIOD_NOT_LOADED",
                "verification_grade": "E",
                "notes": "",
            },
        ]
    )
    source_status = {
        "pre_listing_report_dates": ["2019-12-31"],
        "discovered_but_zero_extraction_dates": ["2020-09-30"],
        "post_listing_missing_report_dates": ["2021-06-30"],
    }
    result = apply_lifecycle_statuses(comparison, source_status)
    assert result["status"].tolist() == [
        "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
        "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
    ]


def test_lifecycle_period_frame_is_complete() -> None:
    source_status = {
        "exchange": "SH",
        "security_lifecycle": {
            "security_code": "688521",
            "exchange": "SH",
            "listing_date": "2020-08-18",
            "listing_date_source": "SSE_COMPANY_PROFILE",
            "requested_report_dates": ["2019-12-31", "2020-09-30", "2020-12-31"],
            "pre_listing_report_dates": ["2019-12-31"],
            "periodic_expected_report_dates": ["2020-09-30", "2020-12-31"],
            "listing_transition_report_dates": ["2020-09-30"],
        },
        "available_report_dates": ["2020-09-30", "2020-12-31"],
        "discovered_but_zero_extraction_dates": ["2020-09-30"],
        "post_listing_missing_report_dates": [],
        "extraction_by_report_date": {"2020-09-30": 0, "2020-12-31": 91},
    }
    frame = lifecycle_period_frame(source_status)
    assert len(frame) == 3
    assert (
        frame.loc[frame["report_date"] == "2019-12-31", "coverage_status"].iloc[0]
        == "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED"
    )
    assert (
        frame.loc[frame["report_date"] == "2020-09-30", "coverage_status"].iloc[0]
        == "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
    )
    assert frame.loc[frame["report_date"] == "2020-12-31", "coverage_status"].iloc[0] == "AVAILABLE"
