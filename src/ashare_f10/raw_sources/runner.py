from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

from ashare_f10.config import Settings, settings
from ashare_f10.raw_sources.downloaders.http_downloader import HttpDownloader, RequestContext
from ashare_f10.raw_sources.downloaders.sse_disclosure import collect_sse_documents
from ashare_f10.raw_sources.entity_matcher import build_security_entity, match_entity, normalize_domain
from ashare_f10.raw_sources.models import (
    EntityMatch,
    RawPackArtifacts,
    RawPackRun,
    RawSource,
    SourceDocument,
    stable_document_id,
    utc_now,
    write_json,
)
from ashare_f10.raw_sources.parsers.html_parser import parse_html_document
from ashare_f10.raw_sources.raw_pack_exporter import export_raw_pack
from ashare_f10.raw_sources.source_manifest import select_sources
from ashare_f10.raw_sources.status_router import (
    route_download_result,
    save_no_match_evidence,
    save_permission_block,
)


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _language(text: str) -> str:
    has_zh = any("\u4e00" <= char <= "\u9fff" for char in text)
    has_en = any("a" <= char.lower() <= "z" for char in text)
    return "mixed" if has_zh and has_en else "zh" if has_zh else "en" if has_en else "unknown"


def _source_url_for_company(source: RawSource, website: str | None) -> str | None:
    if not website:
        return None
    base = website if website.startswith(("http://", "https://")) else f"https://{website}"
    # Stage-validated manifests can provide an exact official subpage.  Reuse it
    # only when its domain matches the F10-confirmed official website; never
    # apply another company's hard-coded path to a new security.
    if normalize_domain(source.base_url) == normalize_domain(base):
        return source.base_url
    if source.source_id == "SRC036":
        return base
    path_by_source = {
        "SRC037": "InvestorRelations",
        "SRC038": "PressRelease",
        "SRC039": "InvestorRelations",
    }
    suffix = path_by_source.get(source.source_id)
    return urljoin(base.rstrip("/") + "/", suffix) if suffix else base


def _collect_company_pages(
    sources: list[RawSource],
    security,
    output_dir: Path,
    downloader: HttpDownloader,
    max_docs: int,
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    seen_urls: set[str] = set()
    for source in sources:
        if len(documents) >= max_docs:
            break
        url = _source_url_for_company(source, security.official_website)
        if not url:
            documents.append(
                SourceDocument(
                    document_id=stable_document_id(security.security_code, source.source_id, "NO_WEBSITE"),
                    security_code=security.security_code,
                    pack_id=source.pack_id,
                    source_id=source.source_id,
                    source_tier=source.source_tier,
                    source_organization=source.official_organization,
                    source_domain=normalize_domain(source.base_url),
                    source_url=source.base_url,
                    document_title=f"{source.name}: official website unavailable",
                    document_type="WEBSITE_PAGE",
                    status="UNRESOLVED",
                    access_status="UNKNOWN",
                    query=security.company_full_name_cn or security.security_code,
                    search_scope="F10 official website field",
                    notes="F10 profile did not provide an official website URL.",
                )
            )
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
        parsed_dir = output_dir / "parsed_sources" / source.pack_id / source.source_id
        expected = normalize_domain(security.official_website)
        result = downloader.snapshot_html(
            url,
            raw_dir,
            RequestContext(
                source_id=source.source_id,
                referer=security.official_website,
                expected_domains=(expected,) if expected else (),
                max_attempts=source.max_attempts,
                rate_limit_seconds=source.rate_limit_seconds,
            ),
        )
        match = match_entity(
            {
                "url": result.final_url or url,
                "text": result.html_text or "",
                "name": security.company_full_name_cn,
            },
            security,
        )
        document = route_download_result(
            result,
            source,
            security,
            match,
            status_on_success="COMPANY_CLAIM",
            document_type="WEBSITE_PAGE",
            document_title=source.name,
            query=security.company_full_name_cn or security.security_code,
            search_scope="official company website page",
        )
        if result.access_status == "DOWNLOAD_OK" and result.file_path:
            parsed = parse_html_document(
                Path(result.file_path),
                result.final_url,
                document_id=document.document_id,
                output_dir=parsed_dir,
            )
            document.parsed_text_saved = bool(parsed.text)
            document.parsed_text_path = parsed.text_path
            document.text_sha256 = parsed.text_sha256
            document.language = _language(parsed.text)  # type: ignore[assignment]
            document.links = parsed.links
            document.canonical_url = parsed.canonical_url
            document.document_title = parsed.title or document.document_title
            document.notes = f"Company official page; parser quality={parsed.quality}"
        documents.append(document)
    return documents


def _collect_seed_page(
    source: RawSource,
    security,
    output_dir: Path,
    downloader: HttpDownloader,
) -> list[SourceDocument]:
    urls = source.seed_urls_by_security.get(security.security_code, [])
    if not urls:
        return [
            save_no_match_evidence(
                security.security_code,
                source,
                security,
                "configured official seed URLs",
                notes="No verified seed URL is configured for this security; no negative business inference.",
            )
        ]
    documents: list[SourceDocument] = []
    for url in urls:
        raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
        parsed_dir = output_dir / "parsed_sources" / source.pack_id / source.source_id
        result = downloader.snapshot_html(
            url,
            raw_dir,
            RequestContext(
                source_id=source.source_id,
                referer=source.base_url,
                expected_domains=tuple(source.expected_domains),
                max_attempts=source.max_attempts,
                rate_limit_seconds=source.rate_limit_seconds,
            ),
        )
        match = match_entity(
            {
                "security_code": security.security_code,
                "url": result.final_url,
                "text": result.html_text or "",
            },
            security,
        )
        document = route_download_result(
            result,
            source,
            security,
            match,
            status_on_success="PRIMARY_NONSTATUTORY",
            document_type="WEBSITE_PAGE",
            document_title=f"{security.security_name_abbr or security.security_code} official IR/roadshow page",
            query=security.security_code,
            search_scope="verified exchange-system seed URL",
        )
        if result.access_status == "DOWNLOAD_OK" and result.file_path:
            parsed = parse_html_document(
                Path(result.file_path),
                result.final_url,
                document_id=document.document_id,
                output_dir=parsed_dir,
            )
            document.parsed_text_saved = bool(parsed.text)
            document.parsed_text_path = parsed.text_path
            document.text_sha256 = parsed.text_sha256
            document.language = _language(parsed.text)  # type: ignore[assignment]
            document.links = parsed.links
            document.document_title = parsed.title or document.document_title
        documents.append(document)
    return documents


def _probe_source(
    source: RawSource,
    security,
    output_dir: Path,
    downloader: HttpDownloader,
) -> list[SourceDocument]:
    url = source.probe_url or source.base_url
    raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
    result = downloader.snapshot_html(
        url,
        raw_dir,
        RequestContext(
            source_id=source.source_id,
            referer=source.base_url,
            expected_domains=tuple(source.expected_domains),
            max_attempts=1,
            rate_limit_seconds=source.rate_limit_seconds,
            permission_gate=True,
        ),
    )
    query = security.company_full_name_cn or security.security_code
    if result.access_status in {"HTTP_403", "JS_REQUIRED", "LOGIN_REQUIRED", "CAPTCHA_REQUIRED"}:
        return [
            save_permission_block(
                result,
                source,
                security,
                query,
                "Use a compliant browser session or provide one official export; retry this source only.",
                "The source-specific official registry or risk evidence remains unavailable.",
            )
        ]
    if result.access_status != "DOWNLOAD_OK":
        return [
            SourceDocument(
                document_id=stable_document_id(
                    security.security_code, source.source_id, result.access_status
                ),
                security_code=security.security_code,
                pack_id=source.pack_id,
                source_id=source.source_id,
                source_tier=source.source_tier,
                source_organization=source.official_organization,
                source_domain=normalize_domain(result.final_url or source.base_url),
                source_url=result.final_url or source.base_url,
                document_title=f"{source.name} access probe",
                document_type="UNKNOWN",
                status="UNRESOLVED",
                access_status=result.access_status,
                query=query,
                search_scope="single official entrance access probe",
                notes=result.error or "Official source access probe failed.",
            )
        ]
    text = result.html_text or ""
    if query and query in text:
        match = match_entity(
            {"name": query, "text": text, "url": result.final_url}, security, {"high_risk_name_match": True}
        )
        document = route_download_result(
            result,
            source,
            security,
            match,
            status_on_success="INDEX_ONLY",
            document_type="UNKNOWN",
            document_title=f"{source.name} accessible entrance with entity text",
            query=query,
            search_scope="single official entrance page",
        )
        return [document]
    return [
        save_no_match_evidence(
            query,
            source,
            security,
            "single official entrance page; no dynamic search was bypassed",
            notes="The official entrance was reachable, but this static probe found no exact entity text.",
        )
    ]


def _collect_index_probe(
    source: RawSource,
    security,
    output_dir: Path,
    downloader: HttpDownloader,
) -> list[SourceDocument]:
    raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
    result = downloader.snapshot_html(
        source.base_url,
        raw_dir,
        RequestContext(
            source_id=source.source_id,
            referer=source.base_url,
            expected_domains=tuple(source.expected_domains),
            max_attempts=min(source.max_attempts, 2),
            rate_limit_seconds=source.rate_limit_seconds,
        ),
    )
    query = " | ".join(
        item
        for item in (
            security.security_code,
            security.company_full_name_cn,
            security.company_full_name_en or "",
            security.security_name_abbr,
        )
        if item
    )
    if result.access_status in {"HTTP_403", "JS_REQUIRED", "LOGIN_REQUIRED", "CAPTCHA_REQUIRED"}:
        return [
            save_permission_block(
                result,
                source,
                security,
                query,
                "Use the official site's browser search or provide an official export once.",
                "Exact entity search from this source is unavailable in this run.",
            )
        ]
    if result.access_status != "DOWNLOAD_OK":
        return [
            SourceDocument(
                document_id=stable_document_id(
                    security.security_code, source.source_id, result.access_status
                ),
                security_code=security.security_code,
                pack_id=source.pack_id,
                source_id=source.source_id,
                source_tier=source.source_tier,
                source_organization=source.official_organization,
                source_domain=normalize_domain(result.final_url or source.base_url),
                source_url=result.final_url or source.base_url,
                document_title=f"{source.name} index probe",
                status="UNRESOLVED",
                access_status=result.access_status,
                query=query,
                search_scope="official entrance page",
                notes=result.error or "Index probe did not complete.",
            )
        ]
    text = re.sub(r"\s+", " ", result.html_text or "")
    exact_terms = [
        security.company_full_name_cn,
        security.company_full_name_en or "",
        security.secucode,
    ]
    if any(term and term in text for term in exact_terms):
        match = match_entity(
            {"name": security.company_full_name_cn, "text": text, "url": result.final_url}, security
        )
        document = route_download_result(
            result,
            source,
            security,
            match,
            status_on_success="INDEX_ONLY",
            document_type="UNKNOWN",
            document_title=f"{source.name} exact-entity entrance hit",
            query=query,
            search_scope="official entrance page",
        )
        return [document]
    return [
        save_no_match_evidence(
            query,
            source,
            security,
            "official entrance page static text only",
            notes="No exact entity text was found in the accessible static page; dynamic search was not bypassed.",
        )
    ]


def _load_combined(run_dir: Path | None) -> dict:
    if not run_dir:
        return {}
    path = run_dir / "combined.json" if run_dir.is_dir() else run_dir
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _update_f10_artifacts(run_dir: Path | None, artifacts: RawPackArtifacts) -> None:
    if run_dir is None:
        return
    artifacts_path = run_dir / "artifacts.json"
    payload: dict = {}
    if artifacts_path.exists():
        payload = json.loads(artifacts_path.read_text(encoding="utf-8"))
    payload["raw_pack"] = artifacts.output_dir
    payload["raw_pack_manifest"] = artifacts.run_manifest
    payload["raw_pack_excel"] = artifacts.excel_index
    payload["raw_pack_parquet"] = artifacts.parquet_index
    payload["raw_pack_duckdb"] = artifacts.duckdb_index
    write_json(artifacts_path, payload)


def run_raw_pack(
    stock_code: str,
    output_root: Path,
    *,
    f10_run_dir: Path | None = None,
    packs: str | list[str] | None = "default",
    max_docs: int = 200,
    config: Settings = settings,
) -> dict:
    combined = _load_combined(f10_run_dir)
    security = build_security_entity(combined, security_code=stock_code)
    sources = select_sources(security, True, packs)
    run_id = _run_id()
    output_dir = output_root / "raw_pack" / security.security_code / run_id
    run = RawPackRun(
        run_id=run_id,
        security=security,
        started_at_utc=utc_now(),
        requested_packs=list(dict.fromkeys(source.pack_id for source in sources)),
        selected_source_ids=[source.source_id for source in sources],
        output_dir=str(output_dir),
    )
    downloader = HttpDownloader(config)
    remaining = max(1, max_docs)
    by_collector: dict[str, list[RawSource]] = {}
    for source in sources:
        by_collector.setdefault(source.collector, []).append(source)

    def append_documents(items: list[SourceDocument]) -> None:
        nonlocal remaining
        for item in items:
            if remaining <= 0:
                break
            run.documents.append(item)
            run.entity_matches.append(
                EntityMatch(
                    matched_entity_id=item.matched_entity_id,
                    relation_to_listed_company=item.relation_to_listed_company,
                    status=item.entity_match_status,
                    confidence=item.entity_match_confidence,
                    matched_fields=["document_contract"],
                    candidate_name=item.document_title or "",
                    evidence=f"copied from SourceDocument {item.document_id}",
                )
            )
            remaining -= 1

    if remaining and by_collector.get("sse_disclosure"):
        source = by_collector["sse_disclosure"][0]
        append_documents(
            collect_sse_documents(
                source,
                security,
                output_dir,
                max_docs=min(4, remaining),
                downloader=downloader,
            )
        )
    if remaining and by_collector.get("company_website"):
        append_documents(
            _collect_company_pages(
                by_collector["company_website"],
                security,
                output_dir,
                downloader,
                min(4, remaining),
            )
        )
    for source in by_collector.get("roadshow_seed", []):
        if remaining <= 0:
            break
        append_documents(_collect_seed_page(source, security, output_dir, downloader))
    for source in by_collector.get("status_probe", []):
        if remaining <= 0:
            break
        append_documents(_probe_source(source, security, output_dir, downloader))
    for source in by_collector.get("index_probe", []):
        if remaining <= 0:
            break
        append_documents(_collect_index_probe(source, security, output_dir, downloader))

    run.completed_at_utc = utc_now()
    artifacts = export_raw_pack(run, output_dir)
    _update_f10_artifacts(f10_run_dir, artifacts)
    summary = {
        "run_id": run.run_id,
        "security": security.model_dump(mode="json"),
        "output_dir": str(output_dir),
        "selected_source_count": len(sources),
        "document_count": len(run.documents),
        "status_counts": run.status_counts(),
        "artifacts": artifacts.model_dump(mode="json"),
        "errors": run.errors,
    }
    reports_dir = output_root / "reports" / security.security_code
    write_json(reports_dir / "raw_pack_summary.json", summary)
    return summary
