from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.derived import (
    derive_independent_quarters,
    evaluate_simple_formula,
)


def test_safe_formula() -> None:
    assert (
        evaluate_simple_formula(
            "TOTAL_LIABILITIES / TOTAL_ASSETS * 100",
            {"TOTAL_LIABILITIES": 40, "TOTAL_ASSETS": 100},
        )
        == 40
    )


def test_quarter_derivation() -> None:
    base = {
        "security_code": "688521",
        "statement_type": "income_statement",
        "scope": "consolidated",
        "field_key": "OPERATE_INCOME",
        "field_name_cn": "营业收入",
        "value_text": "",
        "unit": "元",
        "normalized_unit": "元",
        "theme": "官方披露",
        "family": "OFFICIAL_DISCLOSURE",
        "dataset": "报告",
        "record_key": "",
        "event_date": None,
        "period_type": "",
        "data_semantics": "flow",
        "field_category": "PAGE_DISPLAY_FIELD",
        "source_url": "",
        "source_document": "报告",
        "source_page": 1,
        "source_row": "",
        "precision_tolerance": 1.0,
        "confidence": "high",
        "source_status": "FACT_DIRECT",
    }
    frame = pd.DataFrame(
        [
            {**base, "report_date": "2025-03-31", "value_num": 100.0},
            {**base, "report_date": "2025-06-30", "value_num": 250.0},
            {**base, "report_date": "2025-09-30", "value_num": 450.0},
            {**base, "report_date": "2025-12-31", "value_num": 800.0},
        ]
    )
    derived = derive_independent_quarters(frame)
    values = dict(zip(derived.period_type, derived.value_num, strict=True))
    assert values == {"Q2": 150.0, "Q3": 200.0, "Q4": 350.0}


def test_document_metadata_includes_derived_independent_quarter_variants():
    import pandas as pd

    from ashare_f10.cross_validation.derived import derive_document_metadata

    documents = pd.DataFrame(
        [
            {
                "source": "SSE",
                "security_code": "688521",
                "title": "芯原股份2025年年度报告",
                "publish_date": "2026-04-01",
                "report_date": "2025-12-31",
                "report_kind": "annual",
                "url": "https://example.test/annual.pdf",
            }
        ]
    )
    metadata = derive_document_metadata(documents)
    assert set(metadata["period_type"]) == {"FY", "Q4"}
    q4 = metadata[(metadata["period_type"] == "Q4") & (metadata["field_key"] == "REPORT_TYPE")].iloc[0]
    assert q4["value_text"] == "四季度"
    assert q4["source_status"] == "FACT_CALCULATED"
    fy = metadata[(metadata["period_type"] == "FY") & (metadata["field_key"] == "REPORT_DATE_NAME")].iloc[0]
    assert fy["value_text"] == "2025年报"
    assert fy["source_status"] == "FACT_DIRECT"
