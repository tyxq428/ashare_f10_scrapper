from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SourceTier = Literal[
    "T0_STATUTORY",
    "T1_GOV_OFFICIAL",
    "T2_COMPANY_OFFICIAL",
    "T3_AUTHORIZED",
    "T4_SECONDARY",
    "T5_UNVERIFIED",
]
DocumentStatus = Literal[
    "FACT_DIRECT",
    "COMPANY_CLAIM",
    "PRIMARY_NONSTATUTORY",
    "SECONDARY_SOURCE",
    "INDEX_ONLY",
    "NO_MATCH",
    "PERMISSION_BLOCKED",
    "UNRESOLVED",
]
EntityMatchStatus = Literal[
    "EXACT_ID_MATCH",
    "EXACT_NAME_MATCH",
    "SUBSIDIARY_MATCH",
    "HISTORICAL_NAME_MATCH",
    "BRAND_DOMAIN_MATCH",
    "AMBIGUOUS_NAME_MATCH",
    "NO_MATCH",
    "UNRESOLVED",
]
AccessStatus = Literal[
    "HTTP_200",
    "HTTP_403",
    "HTTP_404",
    "JS_REQUIRED",
    "LOGIN_REQUIRED",
    "CAPTCHA_REQUIRED",
    "NO_EXACT_HIT",
    "DOWNLOAD_OK",
    "DOWNLOAD_FAILED",
    "PARSE_FAILED",
    "TIMEOUT",
    "UNKNOWN",
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_document_id(*parts: Any) -> str:
    payload = "|".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class SecurityEntity(BaseModel):
    security_code: str
    secucode: str
    security_name_abbr: str = ""
    company_full_name_cn: str = ""
    company_full_name_en: str | None = None
    unified_social_credit_code: str | None = None
    former_names: list[str] = Field(default_factory=list)
    official_website: str | None = None
    listed_market: Literal["SSE", "SZSE", "BSE", "UNKNOWN"] = "UNKNOWN"
    industry_keywords: list[str] = Field(default_factory=list)
    brand_keywords: list[str] = Field(default_factory=list)
    subsidiaries: list[dict[str, Any]] = Field(default_factory=list)
    entity_source: str = "F10"

    @field_validator("security_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) != 6:
            raise ValueError("security_code must contain exactly six digits")
        return digits


class EntityMatch(BaseModel):
    matched_entity_id: str | None = None
    relation_to_listed_company: Literal["LISTED_PARENT", "SUBSIDIARY", "ASSOCIATE", "BRAND", "UNKNOWN"] = (
        "UNKNOWN"
    )
    status: EntityMatchStatus
    confidence: Literal["very_high", "high", "medium_high", "medium", "low", "none", "unresolved"]
    matched_fields: list[str] = Field(default_factory=list)
    candidate_name: str = ""
    evidence: str = ""


class Attachment(BaseModel):
    attachment_id: str
    parent_document_id: str
    source_url: str
    file_name: str | None = None
    content_type: str | None = None
    file_path: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    status: Literal["DOWNLOAD_OK", "DOWNLOAD_FAILED", "PERMISSION_BLOCKED", "UNRESOLVED"]
    notes: str = ""


class SourceDocument(BaseModel):
    document_id: str
    security_code: str
    matched_entity_id: str | None = None
    relation_to_listed_company: Literal["LISTED_PARENT", "SUBSIDIARY", "ASSOCIATE", "BRAND", "UNKNOWN"] = (
        "UNKNOWN"
    )
    entity_match_status: EntityMatchStatus = "UNRESOLVED"
    entity_match_confidence: Literal[
        "very_high", "high", "medium_high", "medium", "low", "none", "unresolved"
    ] = "unresolved"
    pack_id: str
    source_id: str
    source_tier: SourceTier
    source_organization: str
    source_domain: str
    source_url: str
    canonical_url: str | None = None
    document_title: str | None = None
    document_type: Literal[
        "ANNOUNCEMENT",
        "PERIODIC_REPORT",
        "PROSPECTUS",
        "REGULATORY",
        "WEBSITE_PAGE",
        "PATENT",
        "TRADEMARK",
        "PROCUREMENT",
        "JUDICIAL",
        "LICENSE",
        "BOND",
        "OVERSEAS",
        "MACRO",
        "NEWS",
        "RESEARCH",
        "UNKNOWN",
    ] = "UNKNOWN"
    publish_date: str | None = None
    report_period: str | None = None
    retrieved_at_utc: str = Field(default_factory=utc_now)
    status: DocumentStatus
    access_status: AccessStatus = "UNKNOWN"
    raw_original_binary_saved: bool = False
    html_snapshot_saved: bool = False
    parsed_text_saved: bool = False
    original_file_path: str | None = None
    parsed_text_path: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    text_sha256: str | None = None
    language: Literal["zh", "en", "mixed", "unknown"] = "unknown"
    page_count: int | None = None
    section_index: list[dict[str, Any]] | None = None
    table_index: list[dict[str, Any]] | None = None
    links: list[str] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    query: str | None = None
    search_scope: str | None = None
    minimum_human_action: str | None = None
    impact_if_not_resolved: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_status_contract(self) -> SourceDocument:
        if self.status == "FACT_DIRECT" and self.source_tier not in {
            "T0_STATUTORY",
            "T1_GOV_OFFICIAL",
            "T3_AUTHORIZED",
        }:
            raise ValueError("FACT_DIRECT requires a primary or authorized source tier")
        if self.status == "SECONDARY_SOURCE" and self.source_tier not in {
            "T3_AUTHORIZED",
            "T4_SECONDARY",
        }:
            raise ValueError("SECONDARY_SOURCE requires T3 or T4 source tier")
        if self.status == "NO_MATCH":
            if not self.query or not self.search_scope:
                raise ValueError("NO_MATCH must preserve query and search_scope")
            if self.file_size_bytes not in (None, 0):
                raise ValueError("NO_MATCH cannot contain a fact value or downloaded source file")
        if self.status == "PERMISSION_BLOCKED" and not self.minimum_human_action:
            raise ValueError("PERMISSION_BLOCKED requires minimum_human_action")
        if self.sha256 is not None and len(self.sha256) != 64:
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return self


class ParsedText(BaseModel):
    document_id: str
    text_path: str | None = None
    text: str = ""
    text_sha256: str
    extractor: Literal["html_text", "pdf_text", "office_text", "manual_export", "unknown"]
    extractor_version: str = "1.0.0"
    page_map: list[dict[str, Any]] | None = None
    quality: Literal["good", "partial", "failed"] = "good"
    title: str | None = None
    canonical_url: str | None = None
    links: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)


class DownloadResult(BaseModel):
    url: str
    final_url: str
    status_code: int | None = None
    access_status: AccessStatus
    content_type: str | None = None
    file_path: str | None = None
    size_bytes: int = 0
    sha256: str | None = None
    html_text: str | None = None
    error: str | None = None
    attempts: int = 1
    retrieved_at_utc: str = Field(default_factory=utc_now)


class RawSource(BaseModel):
    source_id: str
    name: str
    pack_id: str
    source_tier: SourceTier
    official_organization: str
    base_url: str
    expected_domains: list[str] = Field(default_factory=list)
    default_policy: str
    priority: str
    applicable_condition: str = ""
    collector: str = "not_implemented"
    implemented: bool = False
    default_enabled: bool = False
    rate_limit_seconds: float = 1.0
    max_attempts: int = 1
    status_on_empty: str = "NO_MATCH"
    probe_url: str | None = None
    seed_urls_by_security: dict[str, list[str]] = Field(default_factory=dict)
    notes: str = ""


class PackPolicy(BaseModel):
    pack_id: str
    default_policy: str
    description: str = ""


class RawSourceManifest(BaseModel):
    schema_version: str
    packs: dict[str, dict[str, Any]]
    sources: list[RawSource]
    default_packs: list[str]
    status_labels: list[str]


class RawPackRun(BaseModel):
    run_id: str
    security: SecurityEntity
    started_at_utc: str
    completed_at_utc: str | None = None
    requested_packs: list[str] = Field(default_factory=list)
    selected_source_ids: list[str] = Field(default_factory=list)
    documents: list[SourceDocument] = Field(default_factory=list)
    entity_matches: list[EntityMatch] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    output_dir: str

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for document in self.documents:
            counts[document.status] = counts.get(document.status, 0) + 1
        return counts

    def to_manifest(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["status_counts"] = self.status_counts()
        return payload


class RawPackArtifacts(BaseModel):
    output_dir: str
    run_manifest: str
    source_documents_jsonl: str
    attachments_jsonl: str
    entity_matches_json: str
    quality_report_json: str
    excel_index: str
    parquet_index: str | None = None
    duckdb_index: str | None = None
    latest_pointer: str


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
