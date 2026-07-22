from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ValidationMode = Literal[
    "OFFICIAL_DIRECT",
    "OFFICIAL_DERIVED",
    "OFFICIAL_DOCUMENT_EVENT",
    "OFFICIAL_METADATA",
    "NOT_IN_PERIODIC_REPORT_SCOPE",
    "EASTMONEY_SOURCE_SPECIFIC",
    "FUTURE_FREE_SOURCE_REQUIRED",
]

ComparisonStatus = Literal[
    "EXACT_MATCH",
    "WITHIN_ROUNDING",
    "DERIVED_MATCH",
    "TEXT_MATCH_NORMALIZED",
    "SET_MATCH",
    "MISMATCH",
    "MISSING_OFFICIAL",
    "MISSING_EASTMONEY",
    "NOT_IN_OFFICIAL_SCOPE",
    "SOURCE_SPECIFIC",
    "FUTURE_FREE_SOURCE_REQUIRED",
    "OFFICIAL_PERIOD_NOT_LOADED",
    "OFFICIAL_SOURCE_UNAVAILABLE",
    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
    "VERSION_CONFLICT",
    "SCOPE_CONFLICT",
    "PERIOD_CONFLICT",
    "UNIT_CONFLICT",
    "UNRESOLVED",
]


@dataclass(slots=True)
class RegistryEntry:
    theme: str
    family: str
    dataset: str
    field_key: str
    field_name_cn: str
    validation_mode: ValidationMode
    statement_type: str = ""
    scope: str = ""
    data_semantics: str = ""
    unit: str = ""
    formula: str = ""
    reason: str = ""
    registry_rule: str = ""
    confidence: str = "high"
    comparison_method: str = "auto"
    canonical_unit: str = ""
    absolute_tolerance: float | None = None
    relative_tolerance: float | None = None
    display_decimals: int | None = None

    @property
    def expected_official(self) -> bool:
        return self.validation_mode in {
            "OFFICIAL_DIRECT",
            "OFFICIAL_DERIVED",
            "OFFICIAL_DOCUMENT_EVENT",
            "OFFICIAL_METADATA",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComparisonRecord:
    comparison_key: str
    security_code: str
    report_date: str | None
    event_date: str | None
    period_type: str
    statement_type: str
    scope: str
    theme: str
    family: str
    dataset: str
    field_key: str
    field_name_cn: str
    validation_mode: ValidationMode
    eastmoney_value_num: float | None
    eastmoney_value_text: str | None
    eastmoney_unit: str
    official_value_num: float | None
    official_value_text: str | None
    official_unit: str
    difference: float | None
    relative_difference: float | None
    tolerance: float | None
    status: ComparisonStatus
    verification_grade: str
    source_document: str = ""
    source_url: str = ""
    source_page: int | None = None
    source_row: str = ""
    eastmoney_source_url: str = ""
    notes: str = ""
    comparison_method: str = ""
    root_cause: str = ""
    absolute_tolerance: float | None = None
    relative_tolerance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CrossValidationArtifacts:
    output_dir: Path
    eastmoney_json: Path
    eastmoney_excel: Path
    eastmoney_parquet: Path
    eastmoney_duckdb: Path
    official_json: Path
    official_excel: Path
    official_parquet: Path
    official_duckdb: Path
    comparison_json: Path
    comparison_excel: Path
    comparison_parquet: Path
    comparison_duckdb: Path
    summary_json: Path
    evidence_zip: Path

    def to_dict(self) -> dict[str, str]:
        return {name: str(value) for name, value in asdict(self).items()}


@dataclass(slots=True)
class CrossValidationSummary:
    security_code: str
    schema_version: str
    registry_version: str
    eastmoney_fact_count: int
    official_fact_count: int
    comparison_count: int
    unique_field_contexts: int
    classified_field_contexts: int
    classification_coverage: float
    status_counts: dict[str, int] = field(default_factory=dict)
    mode_counts: dict[str, int] = field(default_factory=dict)
    true_conflict_count: int = 0
    comparable_count: int = 0
    matched_count: int = 0
    comparable_match_rate: float | None = None
    comparison_coverage: float | None = None
    comparison_accuracy: float | None = None
    evidence_completeness: float | None = None
    unresolved_rate: float | None = None
    suspicious_extraction_rate: float | None = None
    paid_sources_used: bool = False
    manual_review_required: bool = False
    acceptance_status: str = "UNKNOWN"
    completed_at_utc: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
