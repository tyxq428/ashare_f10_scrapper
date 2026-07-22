from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonicalObservation:
    observation_id: str
    security_code: str
    metric_id: str
    metric_name_cn: str
    research_module: str
    report_date: str | None
    event_date: str | None
    period_type: str
    data_semantics: str
    scope: str
    value_num: float | None
    value_text: str | None
    unit: str
    status: str
    confidence: str
    selected_source_fact_id: str
    source_count: int
    usable_source_count: int
    conflict_count: int
    as_of_date: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FactLineage:
    lineage_id: str
    observation_id: str
    source_fact_id: str
    role: str
    source_priority: int
    source_name: str
    source_status: str
    selection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MappingCoverage:
    source_fact_count: int = 0
    mapped_source_fact_count: int = 0
    fallback_source_fact_count: int = 0
    quarantined_source_fact_count: int = 0
    canonical_observation_count: int = 0
    verified_multi_source_count: int = 0
    single_source_count: int = 0
    source_conflict_count: int = 0
    research_module_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mapping_coverage"] = (
            None
            if self.source_fact_count == 0
            else self.mapped_source_fact_count / self.source_fact_count
        )
        return payload
