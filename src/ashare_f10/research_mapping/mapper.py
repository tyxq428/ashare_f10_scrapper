from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

from ashare_f10.research_mapping.models import (
    CanonicalObservation,
    FactLineage,
    MappingCoverage,
)
from ashare_f10.research_mapping.ontology import MetricDefinition, ResearchOntology
from ashare_f10.validation.point_in_time import normalize_date

UNIT_SCALES = {
    "元": 1.0,
    "千元": 1_000.0,
    "万元": 10_000.0,
    "亿元": 100_000_000.0,
}
QUARANTINED_STATUSES = {"PARSE_SUSPECT", "UNRESOLVED"}
SOURCE_PRIORITIES = {
    ("OFFICIAL_DISCLOSURE", "FACT_DIRECT"): 100,
    ("OFFICIAL_DISCLOSURE", "FACT_CALCULATED"): 90,
    ("OFFICIAL_DISCLOSURE", "OFFICIAL_METADATA"): 85,
    ("EASTMONEY", "FACT_DIRECT"): 60,
    ("EASTMONEY", "FACT_CALCULATED"): 55,
    ("EASTMONEY", "SOURCE_SPECIFIC"): 40,
}


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)


def _normalize_unit_value(
    value_num: float | None,
    unit: str,
    definition: MetricDefinition,
) -> tuple[float | None, str]:
    clean_unit = str(unit or "").strip()
    canonical_unit = definition.canonical_unit or clean_unit
    if value_num is None:
        return None, canonical_unit
    if clean_unit in UNIT_SCALES and canonical_unit == "元":
        return value_num * UNIT_SCALES[clean_unit], canonical_unit
    return value_num, canonical_unit


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")").replace("，", ",")
    return re.sub(r"[\s\u3000]+", "", text)


def _same_value(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_num = _number(left.get("normalized_value_num"))
    right_num = _number(right.get("normalized_value_num"))
    if left_num is not None and right_num is not None:
        denominator = max(abs(left_num), abs(right_num), 1.0)
        return abs(left_num - right_num) <= max(1e-9, denominator * 1e-10)
    return _normalize_text(left.get("value_text")) == _normalize_text(right.get("value_text"))


def _source_name(row: dict[str, Any]) -> str:
    explicit = str(row.get("source") or "").upper()
    if explicit:
        return explicit
    family = str(row.get("family") or "")
    return "OFFICIAL_DISCLOSURE" if family == "OFFICIAL_DISCLOSURE" else "EASTMONEY"


def _source_priority(source_name: str, source_status: str) -> int:
    if source_status in QUARANTINED_STATUSES:
        return 0
    return SOURCE_PRIORITIES.get((source_name, source_status), 50 if source_name == "EASTMONEY" else 70)


def _scope(row: dict[str, Any], definition: MetricDefinition) -> str:
    value = str(row.get("scope") or "").strip()
    return value or definition.preferred_scope or "entity"


def _period_type(row: dict[str, Any]) -> str:
    return str(row.get("period_type") or "OTHER")


def _availability(row: dict[str, Any]) -> str:
    value = str(row.get("available_at") or "").strip()
    if value:
        try:
            return normalize_date(value)
        except ValueError:
            return value
    return ""


@dataclass(slots=True)
class ResearchMappingResult:
    source_facts: pd.DataFrame
    canonical_observations: pd.DataFrame
    lineage: pd.DataFrame
    research_views: dict[str, pd.DataFrame]
    coverage: dict[str, Any]


class ResearchMapper:
    def __init__(
        self,
        ontology: ResearchOntology | None = None,
        *,
        as_of_date: str | None = None,
    ) -> None:
        self.ontology = ontology or ResearchOntology()
        self.as_of_date = normalize_date(as_of_date, default_today=True)

    def _source_facts(self, frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, MappingCoverage]:
        records: list[dict[str, Any]] = []
        coverage = MappingCoverage()
        for frame in frames:
            if frame is None or frame.empty:
                continue
            for row in frame.to_dict("records"):
                source_name = _source_name(row)
                source_status = str(row.get("source_status") or "FACT_DIRECT")
                available_at = _availability(row)
                if available_at and available_at > self.as_of_date:
                    continue
                definition, explicitly_mapped = self.ontology.resolve(row)
                value_num = _number(row.get("value_num"))
                normalized_value_num, normalized_unit = _normalize_unit_value(
                    value_num,
                    str(row.get("normalized_unit") or row.get("unit") or ""),
                    definition,
                )
                source_fact_id = _stable_id(
                    "sf",
                    source_name,
                    row.get("security_code"),
                    row.get("family"),
                    row.get("dataset"),
                    row.get("record_key"),
                    row.get("field_key"),
                    row.get("report_date"),
                    row.get("event_date"),
                    row.get("period_type"),
                    row.get("scope"),
                    row.get("value_num"),
                    row.get("value_text"),
                    row.get("source_url"),
                    row.get("document_id"),
                )
                record = {
                    "source_fact_id": source_fact_id,
                    "security_code": str(row.get("security_code") or ""),
                    "metric_id": definition.metric_id,
                    "metric_name_cn": definition.name_cn,
                    "research_module": definition.research_module,
                    "explicitly_mapped": explicitly_mapped,
                    "source_name": source_name,
                    "source_priority": _source_priority(source_name, source_status),
                    "source_status": source_status,
                    "report_date": _text(row.get("report_date")),
                    "event_date": _text(row.get("event_date")),
                    "period_type": _period_type(row),
                    "data_semantics": str(
                        row.get("data_semantics") or definition.data_semantics or "event"
                    ),
                    "scope": _scope(row, definition),
                    "field_key": str(row.get("field_key") or ""),
                    "field_name_cn": str(row.get("field_name_cn") or row.get("field_key") or ""),
                    "family": str(row.get("family") or ""),
                    "dataset": str(row.get("dataset") or ""),
                    "record_key": str(row.get("record_key") or ""),
                    "value_num": value_num,
                    "normalized_value_num": normalized_value_num,
                    "value_text": _text(row.get("value_text")),
                    "unit": str(row.get("unit") or ""),
                    "normalized_unit": normalized_unit,
                    "available_at": available_at,
                    "source_url": str(row.get("source_url") or ""),
                    "source_document": str(row.get("source_document") or ""),
                    "document_id": str(row.get("document_id") or ""),
                    "source_page": row.get("source_page"),
                    "source_row": str(row.get("source_row") or ""),
                    "quality_flags": json.dumps(row.get("quality_flags") or [], ensure_ascii=False),
                    "is_quarantined": source_status in QUARANTINED_STATUSES,
                }
                records.append(record)
                coverage.source_fact_count += 1
                coverage.mapped_source_fact_count += int(explicitly_mapped)
                coverage.fallback_source_fact_count += int(not explicitly_mapped)
                coverage.quarantined_source_fact_count += int(record["is_quarantined"])
        frame = pd.DataFrame(records)
        if not frame.empty:
            frame = frame.drop_duplicates("source_fact_id", keep="first").reset_index(drop=True)
            coverage.source_fact_count = len(frame)
            coverage.mapped_source_fact_count = int(frame["explicitly_mapped"].sum())
            coverage.fallback_source_fact_count = int((~frame["explicitly_mapped"]).sum())
            coverage.quarantined_source_fact_count = int(frame["is_quarantined"].sum())
        return frame, coverage

    @staticmethod
    def _observation_key(row: dict[str, Any]) -> tuple[str, ...]:
        return (
            str(row.get("security_code") or ""),
            str(row.get("metric_id") or ""),
            str(row.get("report_date") or ""),
            str(row.get("event_date") or ""),
            str(row.get("period_type") or ""),
            str(row.get("data_semantics") or ""),
            str(row.get("scope") or ""),
        )

    def _canonicalize(
        self,
        source_facts: pd.DataFrame,
        coverage: MappingCoverage,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if source_facts.empty:
            return pd.DataFrame(), pd.DataFrame()
        observations: list[dict[str, Any]] = []
        lineage_records: list[dict[str, Any]] = []
        grouped = source_facts.groupby(
            [
                "security_code",
                "metric_id",
                "report_date",
                "event_date",
                "period_type",
                "data_semantics",
                "scope",
            ],
            dropna=False,
            sort=True,
        )
        for _, group in grouped:
            candidates = group.sort_values(
                ["is_quarantined", "source_priority", "available_at", "source_fact_id"],
                ascending=[True, False, False, True],
                na_position="last",
            )
            first = candidates.iloc[0].to_dict()
            observation_id = _stable_id("obs", *self._observation_key(first))
            usable = candidates[~candidates["is_quarantined"]]
            selected: dict[str, Any] | None = None
            status = "UNRESOLVED"
            confidence = "low"
            conflict_ids: set[str] = set()
            if not usable.empty:
                selected = usable.iloc[0].to_dict()
                disagreements = [
                    row
                    for row in usable.iloc[1:].to_dict("records")
                    if not _same_value(selected, row)
                ]
                conflict_ids = {str(item["source_fact_id"]) for item in disagreements}
                if disagreements:
                    status = "SOURCE_CONFLICT"
                    confidence = "low"
                    selected = None
                elif len(usable) > 1:
                    status = "VERIFIED_MULTI_SOURCE"
                    confidence = "high"
                else:
                    status = "SINGLE_SOURCE"
                    confidence = "high" if int(usable.iloc[0]["source_priority"]) >= 85 else "medium"
            observation = CanonicalObservation(
                observation_id=observation_id,
                security_code=str(first["security_code"]),
                metric_id=str(first["metric_id"]),
                metric_name_cn=str(first["metric_name_cn"]),
                research_module=str(first["research_module"]),
                report_date=_text(first.get("report_date")),
                event_date=_text(first.get("event_date")),
                period_type=str(first.get("period_type") or ""),
                data_semantics=str(first.get("data_semantics") or ""),
                scope=str(first.get("scope") or ""),
                value_num=_number(selected.get("normalized_value_num")) if selected else None,
                value_text=_text(selected.get("value_text")) if selected else None,
                unit=str(selected.get("normalized_unit") or "") if selected else str(first.get("normalized_unit") or ""),
                status=status,
                confidence=confidence,
                selected_source_fact_id=str(selected.get("source_fact_id") or "") if selected else "",
                source_count=len(candidates),
                usable_source_count=len(usable),
                conflict_count=len(conflict_ids),
                as_of_date=self.as_of_date,
            )
            observations.append(observation.to_dict())
            for row in candidates.to_dict("records"):
                source_fact_id = str(row["source_fact_id"])
                if bool(row["is_quarantined"]):
                    role = "QUARANTINED"
                    reason = "Parser or source-quality gate excluded the fact from canonical selection"
                elif selected and source_fact_id == selected["source_fact_id"]:
                    role = "SELECTED"
                    reason = "Highest-priority usable source after point-in-time filtering"
                elif source_fact_id in conflict_ids:
                    role = "CONFLICTING"
                    reason = "Value differs from another usable source for the same canonical observation"
                else:
                    role = "SUPPORTING"
                    reason = "Independent source agrees with the selected canonical value"
                lineage_records.append(
                    FactLineage(
                        lineage_id=_stable_id("lin", observation_id, source_fact_id),
                        observation_id=observation_id,
                        source_fact_id=source_fact_id,
                        role=role,
                        source_priority=int(row["source_priority"]),
                        source_name=str(row["source_name"]),
                        source_status=str(row["source_status"]),
                        selection_reason=reason,
                    ).to_dict()
                )
        observation_frame = pd.DataFrame(observations)
        lineage_frame = pd.DataFrame(lineage_records)
        coverage.canonical_observation_count = len(observation_frame)
        if not observation_frame.empty:
            status_counts = Counter(observation_frame["status"])
            coverage.verified_multi_source_count = status_counts["VERIFIED_MULTI_SOURCE"]
            coverage.single_source_count = status_counts["SINGLE_SOURCE"]
            coverage.source_conflict_count = status_counts["SOURCE_CONFLICT"]
            coverage.research_module_counts = dict(Counter(observation_frame["research_module"]))
        return observation_frame, lineage_frame

    @staticmethod
    def _research_views(observations: pd.DataFrame) -> dict[str, pd.DataFrame]:
        modules = (
            "company_master",
            "financial_statements",
            "quarterly_and_ttm",
            "profit_quality",
            "segments_and_kpis",
            "capital_structure",
            "governance_and_events",
            "market_and_consensus",
            "coverage_and_gaps",
        )
        views: dict[str, pd.DataFrame] = {}
        for module in modules:
            if observations.empty:
                views[module] = pd.DataFrame()
                continue
            view = observations[observations["research_module"] == module].copy()
            views[module] = view.sort_values(
                ["metric_id", "report_date", "event_date", "period_type"],
                na_position="last",
            ).reset_index(drop=True)
        return views

    def map(self, *frames: pd.DataFrame) -> ResearchMappingResult:
        source_facts, coverage = self._source_facts(list(frames))
        observations, lineage = self._canonicalize(source_facts, coverage)
        return ResearchMappingResult(
            source_facts=source_facts,
            canonical_observations=observations,
            lineage=lineage,
            research_views=self._research_views(observations),
            coverage=coverage.to_dict(),
        )
