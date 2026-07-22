from __future__ import annotations

import json

import pandas as pd
import pytest

from ashare_f10.research_mapping import ResearchSectionExtractor


def _observation(
    metric_id: str,
    value: float | None,
    *,
    observation_id: str | None = None,
    unit: str = "元",
    status: str = "SINGLE_SOURCE",
) -> dict:
    return {
        "observation_id": observation_id or f"obs-{metric_id}",
        "security_code": "688521",
        "metric_id": metric_id,
        "metric_name_cn": metric_id,
        "research_module": "profit_quality",
        "report_date": "2025-12-31",
        "event_date": None,
        "period_type": "FY",
        "data_semantics": "flow",
        "scope": "consolidated",
        "value_num": value,
        "value_text": None,
        "unit": unit,
        "status": status,
        "confidence": "high",
        "selected_source_fact_id": f"sf-{metric_id}",
        "source_count": 1,
        "usable_source_count": 1,
        "conflict_count": 0,
        "as_of_date": "2026-03-31",
    }


def _source_fact(
    field_key: str,
    *,
    value_num: float | None = None,
    value_text: str | None = None,
    family: str = "RPT_F10_BUSINESS_MAINOP",
    dataset: str = "main_business",
    record_key: str = "segment-1",
    report_date: str = "2025-12-31",
) -> dict:
    return {
        "source_fact_id": f"sf-{family}-{record_key}-{field_key}",
        "security_code": "688521",
        "metric_id": f"source.{family.lower()}.{field_key.lower()}",
        "metric_name_cn": field_key,
        "research_module": "coverage_and_gaps",
        "explicitly_mapped": False,
        "source_name": "EASTMONEY",
        "source_priority": 60,
        "source_status": "FACT_DIRECT",
        "report_date": report_date,
        "event_date": None,
        "period_type": "FY",
        "data_semantics": "flow",
        "scope": "consolidated",
        "field_key": field_key,
        "field_name_cn": field_key,
        "family": family,
        "dataset": dataset,
        "record_key": record_key,
        "value_num": value_num,
        "normalized_value_num": value_num,
        "value_text": value_text,
        "unit": "元" if value_num is not None else "",
        "normalized_unit": "元" if value_num is not None else "",
        "available_at": "2026-03-20",
        "source_url": "https://eastmoney.invalid/api",
        "source_document": family,
        "document_id": "",
        "source_page": None,
        "source_row": record_key,
        "quality_flags": "[]",
        "is_quarantined": False,
    }


def _metric(pack: pd.DataFrame, metric_id: str) -> pd.Series:
    return pack.loc[pack["metric_id"] == metric_id].iloc[-1]


def test_profit_quality_derivations_are_deterministic_and_traceable() -> None:
    observations = pd.DataFrame(
        [
            _observation("financial.parent_net_profit", 100.0),
            _observation("profit_quality.adjusted_parent_net_profit", 80.0),
            _observation("cashflow.operating_cash_flow", 150.0),
            _observation("cashflow.capital_expenditure", 30.0),
            _observation("research.rd_investment", 20.0),
            _observation("research.capitalized_rd", 5.0),
        ]
    )
    result = ResearchSectionExtractor().extract(observations, pd.DataFrame())
    profit = result.profit_quality

    non_recurring = _metric(profit, "profit_quality.non_recurring_amount_calculated")
    assert non_recurring["value_num"] == 20.0
    assert non_recurring["status"] == "FACT_CALCULATED"

    share = _metric(profit, "profit_quality.non_recurring_share")
    assert share["value_num"] == 20.0
    assert share["status"] == "FACT_CALCULATED"
    assert len(json.loads(share["input_ids"])) == 2

    cash_conversion = _metric(profit, "profit_quality.cfo_to_adjusted_profit")
    assert cash_conversion["value_num"] == pytest.approx(1.875)
    assert cash_conversion["status"] == "FACT_CALCULATED"

    fcf = _metric(profit, "profit_quality.simplified_free_cash_flow")
    assert fcf["value_num"] == 120.0
    assert fcf["status"] == "FACT_CALCULATED"
    assert fcf["formula"] == "operating_cash_flow - capital_expenditure"

    rd_rate = _metric(profit, "profit_quality.rd_capitalization_rate")
    assert rd_rate["value_num"] == 25.0
    assert rd_rate["status"] == "FACT_CALCULATED"
    assert not profit["research_fact_id"].duplicated().any()


def test_missing_profit_inputs_remain_unresolved_and_are_never_zero_filled() -> None:
    observations = pd.DataFrame([_observation("financial.parent_net_profit", 100.0)])
    result = ResearchSectionExtractor().extract(observations, pd.DataFrame())
    profit = result.profit_quality
    non_recurring = _metric(profit, "profit_quality.non_recurring_amount_calculated")
    assert pd.isna(non_recurring["value_num"])
    assert non_recurring["status"] == "UNRESOLVED"
    share = _metric(profit, "profit_quality.non_recurring_share")
    assert pd.isna(share["value_num"])
    assert share["status"] == "UNRESOLVED"
    assert "未补零" in non_recurring["notes"]


def test_segment_rows_are_reconstructed_within_record_key_only() -> None:
    source_facts = pd.DataFrame(
        [
            _source_fact("ITEM_NAME", value_text="IP授权", record_key="segment-ip"),
            _source_fact("REVENUE", value_num=100.0, record_key="segment-ip"),
            _source_fact("COST", value_num=60.0, record_key="segment-ip"),
            _source_fact("ITEM_NAME", value_text="芯片定制", record_key="segment-chip"),
            _source_fact("REVENUE", value_num=200.0, record_key="segment-chip"),
            _source_fact("COST", value_num=150.0, record_key="segment-chip"),
        ]
    )
    result = ResearchSectionExtractor().extract(pd.DataFrame(), source_facts)
    segments = result.segments_and_kpis.set_index("segment_name")
    assert set(segments.index) == {"IP授权", "芯片定制"}
    assert segments.loc["IP授权", "profit"] == 40.0
    assert segments.loc["IP授权", "margin_pct"] == 40.0
    assert segments.loc["芯片定制", "profit"] == 50.0
    assert segments.loc["芯片定制", "margin_pct"] == 25.0
    assert segments["segment_record_id"].nunique() == 2


def test_routing_separates_research_capital_governance_and_risk_topics() -> None:
    source_facts = pd.DataFrame(
        [
            _source_fact("RESEARCH_EXPENSE", value_num=10.0, family="RPT_F10_BUSINESS_RDEXPENSE"),
            _source_fact("TOTAL_SHARES", value_num=1_000.0, family="RPT_F10_SHARE_STRUCTURE"),
            _source_fact("PLEDGE_RATIO", value_num=15.0, family="RPT_F10_SHARE_PLEDGE"),
            _source_fact("DIVIDEND_PLAN", value_text="10派2元", family="RPT_F10_DIVIDEND"),
            _source_fact("DIRECTOR_NAME", value_text="张三", family="RPT_F10_DIRECTOR"),
            _source_fact("LITIGATION_TITLE", value_text="合同纠纷", family="RPT_F10_LITIGATION"),
        ]
    )
    result = ResearchSectionExtractor().extract(pd.DataFrame(), source_facts)
    assert "RESEARCH_EXPENSE" in set(result.research_and_development["field_key"])
    assert {"TOTAL_SHARES", "PLEDGE_RATIO"}.issubset(set(result.capital_structure["field_key"]))
    assert "DIVIDEND_PLAN" in set(result.capital_events["field_key"])
    assert "DIRECTOR_NAME" in set(result.corporate_governance["field_key"])
    assert "LITIGATION_TITLE" in set(result.risk_events["field_key"])
    for name, frame in result.tables().items():
        if name != "coverage_gaps" and not frame.empty and "research_fact_id" in frame:
            assert not frame["research_fact_id"].duplicated().any()


def test_coverage_gaps_distinguish_missing_from_zero() -> None:
    observations = pd.DataFrame(
        [
            _observation("financial.parent_net_profit", 0.0),
            _observation("research.rd_expense", 0.0),
            _observation("capital.total_shares", 1_000.0, unit="股"),
        ]
    )
    result = ResearchSectionExtractor().extract(observations, pd.DataFrame())
    gaps = result.coverage_gaps.set_index("required_metric_id")
    assert gaps.loc["financial.parent_net_profit", "status"] == "PRESENT"
    assert gaps.loc["research.rd_expense", "status"] == "PRESENT"
    assert gaps.loc["capital.total_shares", "status"] == "PRESENT"
    assert gaps.loc["profit_quality.adjusted_parent_net_profit", "status"] == "MISSING"
    assert "不得解释为数值为0" in gaps.loc["profit_quality.adjusted_parent_net_profit", "notes"]
    assert gaps.loc["segment_records", "status"] == "MISSING"


def test_research_fact_ids_are_stable_across_repeated_extraction() -> None:
    observations = pd.DataFrame(
        [
            _observation("financial.parent_net_profit", 100.0),
            _observation("profit_quality.adjusted_parent_net_profit", 80.0),
        ]
    )
    extractor = ResearchSectionExtractor()
    first = extractor.extract(observations, pd.DataFrame()).profit_quality
    second = extractor.extract(observations, pd.DataFrame()).profit_quality
    assert list(first["research_fact_id"]) == list(second["research_fact_id"])
