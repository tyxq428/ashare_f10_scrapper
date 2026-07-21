from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class OfficialDocument:
    source: str
    security_code: str
    title: str
    publish_date: str
    report_date: str
    report_kind: str
    version_label: str
    url: str
    local_path: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TargetField:
    field_key: str
    field_name_cn: str
    statement_type: str
    aliases: tuple[str, ...]
    eastmoney_keys: tuple[str, ...]
    eastmoney_families: tuple[str, ...]
    semantics: str = "flow"


@dataclass(slots=True)
class OfficialFact:
    security_code: str
    report_date: str
    statement_type: str
    scope: str
    field_key: str
    field_name_report: str
    value: float
    unit: str
    normalized_unit: str
    source_document: str
    source_url: str
    source_page: int
    source_row: str
    extraction_method: str
    precision_tolerance: float
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReconciliationResult:
    security_code: str
    report_date: str
    statement_type: str
    field_key: str
    field_name_cn: str
    eastmoney_value: float | None
    official_value: float | None
    difference: float | None
    absolute_tolerance: float
    relative_difference: float | None
    status: str
    verification_grade: str
    source_document: str
    source_page: int | None
    source_row: str
    eastmoney_family: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LogicCheck:
    security_code: str
    report_date: str
    check_id: str
    description: str
    left_value: float | None
    right_value: float | None
    difference: float | None
    tolerance: float
    status: str
    source: str
    components: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TTMValidation:
    security_code: str
    field_key: str
    field_name_cn: str
    end_period: str
    independent_quarters_value: float | None
    cumulative_formula_value: float | None
    difference: float | None
    tolerance: float
    status: str
    independent_components: list[dict[str, Any]]
    cumulative_components: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationArtifacts:
    output_dir: Path
    summary_json: Path
    detail_parquet: Path
    official_facts_parquet: Path
    evidence_json: Path
    mismatches_excel: Path
    source_hashes_json: Path

    def to_dict(self) -> dict[str, str]:
        return {name: str(value) for name, value in asdict(self).items()}
