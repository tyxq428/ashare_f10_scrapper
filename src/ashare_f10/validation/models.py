from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_NOTE_REFERENCE_AT_END = re.compile(
    r"(?:附注\s*)?[一二三四五六七八九十百]+\s*[、.．]\s*(?P<note>\d{1,3})"
    r"(?:\s*[（(]\s*\d{1,3}\s*[）)])?\s*$"
)
_MONETARY_STATEMENTS = {"balance_sheet", "income_statement", "cash_flow", "summary"}


def _quality_flags_for_fact(
    source_row: str,
    value: float,
    statement_type: str,
) -> tuple[str, ...]:
    """Detect high-risk parser outputs without guessing a replacement value.

    Official financial statements often place note references between the row label and
    the amount columns.  When PDF table extraction drops the amount cells, a line such as
    ``递延所得税资产 七、29`` can leave ``29`` as the only numeric token.  That token is a
    note number, not an amount.  The quality gate marks the fact as suspicious so that it
    remains auditable but cannot enter reconciliation, logic checks or canonical facts.
    """

    if statement_type not in _MONETARY_STATEMENTS:
        return ()
    row = str(source_row or "").strip()
    match = _NOTE_REFERENCE_AT_END.search(row)
    if match is None:
        return ()
    try:
        note_number = float(match.group("note"))
    except (TypeError, ValueError):
        return ()
    prefix = row[: match.start()]
    # A genuine amount before the note token means the row still contains monetary data;
    # do not reject it here.  The parser may have selected a later amount column.
    if re.search(r"[-−(（]?\d[\d,，]*(?:\.\d+)?", prefix):
        return ()
    if abs(float(value) - note_number) > 1e-12:
        return ()
    return ("NOTE_REFERENCE_AS_AMOUNT",)


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
    source_status: str = "FACT_DIRECT"
    quality_flags: tuple[str, ...] = ()
    parse_notes: str = ""
    raw_value: float | None = None

    def __post_init__(self) -> None:
        if self.raw_value is None:
            self.raw_value = self.value
        detected = _quality_flags_for_fact(self.source_row, self.value, self.statement_type)
        if detected:
            self.quality_flags = tuple(dict.fromkeys((*self.quality_flags, *detected)))
            self.source_status = "PARSE_SUSPECT"
            self.confidence = "low"
            if not self.parse_notes:
                self.parse_notes = (
                    "Only a financial-statement note reference was available as the numeric token; "
                    "the value is quarantined pending row reconstruction or manual review."
                )

    @property
    def usable_for_reconciliation(self) -> bool:
        return self.source_status not in {"PARSE_SUSPECT", "UNRESOLVED"}

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
