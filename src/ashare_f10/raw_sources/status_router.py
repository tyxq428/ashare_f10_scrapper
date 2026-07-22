from __future__ import annotations

from urllib.parse import urlparse

from ashare_f10.raw_sources.models import (
    DocumentStatus,
    DownloadResult,
    EntityMatch,
    RawSource,
    SecurityEntity,
    SourceDocument,
    stable_document_id,
)

_PERMISSION_STATUSES = {"HTTP_403", "JS_REQUIRED", "LOGIN_REQUIRED", "CAPTCHA_REQUIRED"}


def _source_domain(source_url: str) -> str:
    return (urlparse(source_url).hostname or "").lower()


def save_no_match_evidence(
    query: str,
    source: RawSource,
    security: SecurityEntity,
    search_scope: str,
    notes: str = "",
) -> SourceDocument:
    return SourceDocument(
        document_id=stable_document_id(security.security_code, source.source_id, query, "NO_MATCH"),
        security_code=security.security_code,
        matched_entity_id=None,
        relation_to_listed_company="UNKNOWN",
        entity_match_status="NO_MATCH",
        entity_match_confidence="none",
        pack_id=source.pack_id,
        source_id=source.source_id,
        source_tier=source.source_tier,
        source_organization=source.official_organization,
        source_domain=_source_domain(source.base_url),
        source_url=source.base_url,
        document_title=f"{source.name} exact-entity search: no match",
        document_type="UNKNOWN",
        status="NO_MATCH",
        access_status="NO_EXACT_HIT",
        query=query,
        search_scope=search_scope,
        notes=notes
        or "No exact entity match under the recorded search conditions; no negative fact inferred.",
    )


def save_permission_block(
    result: DownloadResult,
    source: RawSource,
    security: SecurityEntity,
    query: str,
    minimum_human_action: str,
    impact_if_not_resolved: str,
) -> SourceDocument:
    return SourceDocument(
        document_id=stable_document_id(security.security_code, source.source_id, query, result.access_status),
        security_code=security.security_code,
        pack_id=source.pack_id,
        source_id=source.source_id,
        source_tier=source.source_tier,
        source_organization=source.official_organization,
        source_domain=_source_domain(result.final_url or source.base_url),
        source_url=result.final_url or source.base_url,
        document_title=f"{source.name} access blocked",
        document_type="UNKNOWN",
        status="PERMISSION_BLOCKED",
        access_status=result.access_status,
        query=query,
        search_scope=source.name,
        minimum_human_action=minimum_human_action,
        impact_if_not_resolved=impact_if_not_resolved,
        notes=result.error or "Permission or dynamic access gate detected; no automatic retry in this run.",
    )


def route_download_result(
    result: DownloadResult,
    source: RawSource,
    security: SecurityEntity,
    entity_match: EntityMatch,
    *,
    status_on_success: DocumentStatus,
    document_type: str,
    document_title: str | None = None,
    query: str | None = None,
    search_scope: str | None = None,
) -> SourceDocument:
    if result.access_status in _PERMISSION_STATUSES:
        return save_permission_block(
            result,
            source,
            security,
            query or source.name,
            "Use a compliant browser session or provide an official export once; resume this source only.",
            "Official evidence from this source remains unavailable, but the overall task continues.",
        )
    if result.access_status != "DOWNLOAD_OK":
        return SourceDocument(
            document_id=stable_document_id(
                security.security_code, source.source_id, result.url, result.access_status
            ),
            security_code=security.security_code,
            matched_entity_id=entity_match.matched_entity_id,
            relation_to_listed_company=entity_match.relation_to_listed_company,
            entity_match_status=entity_match.status,
            entity_match_confidence=entity_match.confidence,
            pack_id=source.pack_id,
            source_id=source.source_id,
            source_tier=source.source_tier,
            source_organization=source.official_organization,
            source_domain=_source_domain(result.final_url or result.url),
            source_url=result.final_url or result.url,
            document_title=document_title or source.name,
            document_type=document_type,
            status="UNRESOLVED",
            access_status=result.access_status,
            query=query,
            search_scope=search_scope,
            notes=result.error or "Download did not complete.",
        )
    return SourceDocument(
        document_id=stable_document_id(
            security.security_code, source.source_id, result.final_url, result.sha256
        ),
        security_code=security.security_code,
        matched_entity_id=entity_match.matched_entity_id,
        relation_to_listed_company=entity_match.relation_to_listed_company,
        entity_match_status=entity_match.status,
        entity_match_confidence=entity_match.confidence,
        pack_id=source.pack_id,
        source_id=source.source_id,
        source_tier=source.source_tier,
        source_organization=source.official_organization,
        source_domain=_source_domain(result.final_url),
        source_url=result.final_url,
        document_title=document_title or source.name,
        document_type=document_type,
        status=status_on_success,
        access_status="DOWNLOAD_OK",
        raw_original_binary_saved=True,
        html_snapshot_saved=bool(result.content_type and "html" in result.content_type),
        original_file_path=result.file_path,
        content_type=result.content_type,
        file_size_bytes=result.size_bytes,
        sha256=result.sha256,
        query=query,
        search_scope=search_scope,
        notes="",
    )
