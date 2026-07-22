from __future__ import annotations

import pandas as pd

from ashare_f10.research_mapping import ResearchMapper


def _fact(
    source: str,
    field_key: str,
    value: float | None,
    *,
    family: str = "RPT_F10_FINANCE_GINCOME",
    dataset: str = "income",
    report_date: str = "2025-12-31",
    period_type: str = "FY",
    source_status: str = "FACT_DIRECT",
    unit: str = "元",
    scope: str = "consolidated",
    available_at: str = "2026-03-20",
    value_text: str | None = None,
) -> dict:
    return {
        "security_code": "688521",
        "source": source,
        "theme": "财务分析" if source == "EASTMONEY" else "官方披露",
        "family": family if source == "EASTMONEY" else "OFFICIAL_DISCLOSURE",
        "dataset": dataset,
        "record_key": f"{source}|{report_date}|{period_type}|{field_key}",
        "report_date": report_date,
        "event_date": None,
        "period_type": period_type,
        "data_semantics": "flow",
        "scope": scope,
        "field_key": field_key,
        "field_name_cn": field_key,
        "value_num": value,
        "value_text": value_text if value_text is not None else (None if value is None else str(value)),
        "unit": unit,
        "normalized_unit": unit,
        "source_status": source_status,
        "source_url": f"https://{source.lower()}.invalid/{field_key}",
        "source_document": "2025年年度报告" if source == "OFFICIAL_DISCLOSURE" else family,
        "document_id": "doc-official" if source == "OFFICIAL_DISCLOSURE" else "",
        "source_page": 80 if source == "OFFICIAL_DISCLOSURE" else None,
        "source_row": field_key,
        "available_at": available_at,
        "quality_flags": [],
    }


def test_official_and_eastmoney_create_one_verified_observation_with_lineage() -> None:
    eastmoney = pd.DataFrame([_fact("EASTMONEY", "OPERATE_INCOME", 1_000_000_000.0)])
    official = pd.DataFrame([_fact("OFFICIAL_DISCLOSURE", "OPERATE_INCOME", 100_000.0, unit="万元")])
    result = ResearchMapper(as_of_date="2026-03-31").map(eastmoney, official)
    assert len(result.source_facts) == 2
    assert len(result.canonical_observations) == 1
    observation = result.canonical_observations.iloc[0]
    assert observation["metric_id"] == "financial.revenue"
    assert observation["status"] == "VERIFIED_MULTI_SOURCE"
    assert observation["value_num"] == 1_000_000_000.0
    assert observation["unit"] == "元"
    assert len(result.lineage) == 2
    assert set(result.lineage["role"]) == {"SELECTED", "SUPPORTING"}


def test_independent_quarter_and_full_year_never_collapse() -> None:
    facts = pd.DataFrame(
        [
            _fact("EASTMONEY", "PARENT_NETPROFIT", 100.0, period_type="FY"),
            _fact("EASTMONEY", "PARENT_NETPROFIT", 25.0, period_type="Q4"),
        ]
    )
    result = ResearchMapper().map(facts)
    assert len(result.canonical_observations) == 2
    assert set(result.canonical_observations["period_type"]) == {"FY", "Q4"}
    assert not result.canonical_observations["observation_id"].duplicated().any()


def test_conflicting_usable_sources_do_not_silently_choose_a_value() -> None:
    official = pd.DataFrame(
        [
            _fact("OFFICIAL_DISCLOSURE", "PARENT_NETPROFIT", 100.0, dataset="original"),
            {
                **_fact("OFFICIAL_DISCLOSURE", "PARENT_NETPROFIT", 120.0, dataset="corrected"),
                "record_key": "official-second-version",
                "document_id": "doc-corrected",
            },
        ]
    )
    result = ResearchMapper().map(official)
    observation = result.canonical_observations.iloc[0]
    assert observation["status"] == "SOURCE_CONFLICT"
    assert pd.isna(observation["value_num"])
    assert observation["selected_source_fact_id"] == ""
    assert set(result.lineage["role"]) == {"SUPPORTING", "CONFLICTING"}


def test_quarantined_parser_fact_is_preserved_but_not_selected() -> None:
    facts = pd.DataFrame(
        [
            _fact("OFFICIAL_DISCLOSURE", "DEFER_TAX_ASSET", 29.0, source_status="PARSE_SUSPECT"),
        ]
    )
    result = ResearchMapper().map(facts)
    assert len(result.source_facts) == 1
    assert result.source_facts.iloc[0]["is_quarantined"]
    observation = result.canonical_observations.iloc[0]
    assert observation["status"] == "UNRESOLVED"
    assert result.lineage.iloc[0]["role"] == "QUARANTINED"


def test_unmapped_fields_receive_stable_fallback_metric_and_gap_view() -> None:
    facts = pd.DataFrame([_fact("EASTMONEY", "UNMAPPED_SPECIAL_FIELD", 42.0, family="CUSTOM_FAMILY")])
    first = ResearchMapper().map(facts)
    second = ResearchMapper().map(facts)
    first_source = first.source_facts.iloc[0]
    assert first_source["metric_id"] == "source.custom_family.unmapped_special_field"
    assert first_source["research_module"] == "coverage_and_gaps"
    assert first_source["source_fact_id"] == second.source_facts.iloc[0]["source_fact_id"]
    assert (
        first.canonical_observations.iloc[0]["observation_id"]
        == second.canonical_observations.iloc[0]["observation_id"]
    )
    assert len(first.research_views["coverage_and_gaps"]) == 1


def test_as_of_date_excludes_future_source_facts() -> None:
    facts = pd.DataFrame(
        [
            _fact("OFFICIAL_DISCLOSURE", "OPERATE_INCOME", 100.0, available_at="2026-04-01"),
            {
                **_fact("EASTMONEY", "OPERATE_INCOME", 90.0, available_at="2026-03-20"),
                "record_key": "eastmoney-before-cutoff",
            },
        ]
    )
    result = ResearchMapper(as_of_date="2026-03-31").map(facts)
    assert len(result.source_facts) == 1
    assert result.source_facts.iloc[0]["source_name"] == "EASTMONEY"
    assert result.canonical_observations.iloc[0]["value_num"] == 90.0
