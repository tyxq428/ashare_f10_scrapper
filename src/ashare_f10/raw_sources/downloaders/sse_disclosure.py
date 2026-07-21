from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from ashare_f10.raw_sources.downloaders.http_downloader import HttpDownloader, RequestContext
from ashare_f10.raw_sources.entity_matcher import match_entity
from ashare_f10.raw_sources.models import RawSource, SecurityEntity, SourceDocument, stable_document_id
from ashare_f10.raw_sources.parsers.html_parser import parse_html_document
from ashare_f10.raw_sources.parsers.pdf_parser import parse_pdf
from ashare_f10.raw_sources.status_router import route_download_result, save_no_match_evidence
from ashare_f10.validation.sources.sse import OfficialSourceError, SSEOfficialSource


def _language(text: str) -> str:
    has_zh = any("\u4e00" <= char <= "\u9fff" for char in text)
    has_en = any("a" <= char.lower() <= "z" for char in text)
    return "mixed" if has_zh and has_en else "zh" if has_zh else "en" if has_en else "unknown"


def _periodic_document(
    source: RawSource,
    security: SecurityEntity,
    official,
    output_dir: Path,
) -> SourceDocument:
    raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
    parsed_dir = output_dir / "parsed_sources" / source.pack_id / source.source_id
    official_source = SSEOfficialSource(timeout=60)
    downloaded = official_source.download(official, raw_dir)
    match = match_entity(
        {
            "security_code": security.security_code,
            "name": security.company_full_name_cn,
            "title": downloaded.title,
        },
        security,
    )
    document_id = stable_document_id(
        security.security_code,
        source.source_id,
        downloaded.url,
        downloaded.sha256,
    )
    parsed = parse_pdf(Path(downloaded.local_path), document_id, parsed_dir)
    path = Path(downloaded.local_path)
    return SourceDocument(
        document_id=document_id,
        security_code=security.security_code,
        matched_entity_id=match.matched_entity_id,
        relation_to_listed_company=match.relation_to_listed_company,
        entity_match_status=match.status,
        entity_match_confidence=match.confidence,
        pack_id=source.pack_id,
        source_id=source.source_id,
        source_tier=source.source_tier,
        source_organization=source.official_organization,
        source_domain="sse.com.cn",
        source_url=downloaded.url,
        document_title=downloaded.title,
        document_type="PERIODIC_REPORT",
        publish_date=downloaded.publish_date or None,
        report_period=downloaded.report_date or None,
        status="FACT_DIRECT",
        access_status="DOWNLOAD_OK",
        raw_original_binary_saved=True,
        parsed_text_saved=bool(parsed.text),
        original_file_path=str(path),
        parsed_text_path=parsed.text_path,
        content_type="application/pdf",
        file_size_bytes=path.stat().st_size,
        sha256=downloaded.sha256,
        text_sha256=parsed.text_sha256,
        language=_language(parsed.text),
        page_count=len(parsed.page_map or []),
        notes=f"SSE official periodic report; parser quality={parsed.quality}",
    )


def _seed_html_documents(
    source: RawSource,
    security: SecurityEntity,
    output_dir: Path,
    downloader: HttpDownloader,
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    urls = source.seed_urls_by_security.get(security.security_code, [])
    for url in urls:
        raw_dir = output_dir / "raw_sources" / source.pack_id / source.source_id
        parsed_dir = output_dir / "parsed_sources" / source.pack_id / source.source_id
        result = downloader.snapshot_html(
            url,
            raw_dir,
            RequestContext(
                source_id=source.source_id,
                referer="https://www.sse.com.cn/",
                expected_domains=tuple(source.expected_domains) or ("sse.com.cn",),
                max_attempts=source.max_attempts,
                rate_limit_seconds=source.rate_limit_seconds,
            ),
        )
        match = match_entity(
            {
                "security_code": security.security_code,
                "name": security.company_full_name_cn,
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
            status_on_success="FACT_DIRECT",
            document_type="ANNOUNCEMENT",
            document_title=f"{security.security_name_abbr or security.security_code} SSE official announcement",
            query=security.security_code,
            search_scope="configured SSE official seed URLs",
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
        documents.append(document)
    return documents


def collect_sse_documents(
    source: RawSource,
    security: SecurityEntity,
    output_dir: Path,
    *,
    max_docs: int = 4,
    downloader: HttpDownloader | None = None,
) -> list[SourceDocument]:
    if security.listed_market != "SSE":
        return []
    downloader = downloader or HttpDownloader()
    documents = _seed_html_documents(source, security, output_dir, downloader)
    remaining = max(0, max_docs - len(documents))
    if remaining <= 0:
        return documents[:max_docs]

    end = date.today()
    begin = end - timedelta(days=5 * 366)
    official_source = SSEOfficialSource(timeout=60)
    try:
        reports = official_source.list_reports(
            security.security_code,
            begin.isoformat(),
            end.isoformat(),
        )
    except OfficialSourceError as exc:
        if documents:
            documents[0].notes = f"{documents[0].notes}; periodic report discovery failed: {exc}"
            return documents
        return [
            save_no_match_evidence(
                security.security_code,
                source,
                security,
                f"SSE periodic report query {begin.isoformat()} to {end.isoformat()}",
                notes=f"SSE query did not return a reusable report set: {exc}",
            )
        ]

    selected = []
    seen_periods: set[str] = set()
    for report in reports:
        if report.report_date in seen_periods:
            continue
        seen_periods.add(report.report_date)
        selected.append(report)
        if len(selected) >= remaining:
            break
    for report in selected:
        try:
            documents.append(_periodic_document(source, security, report, output_dir))
        except Exception as exc:  # noqa: BLE001
            documents.append(
                SourceDocument(
                    document_id=stable_document_id(
                        security.security_code, source.source_id, report.url, "UNRESOLVED"
                    ),
                    security_code=security.security_code,
                    matched_entity_id=security.secucode,
                    relation_to_listed_company="LISTED_PARENT",
                    entity_match_status="EXACT_ID_MATCH",
                    entity_match_confidence="very_high",
                    pack_id=source.pack_id,
                    source_id=source.source_id,
                    source_tier=source.source_tier,
                    source_organization=source.official_organization,
                    source_domain="sse.com.cn",
                    source_url=report.url,
                    document_title=report.title,
                    document_type="PERIODIC_REPORT",
                    publish_date=report.publish_date or None,
                    report_period=report.report_date or None,
                    status="UNRESOLVED",
                    access_status="DOWNLOAD_FAILED",
                    query=security.security_code,
                    search_scope="SSE periodic reports",
                    notes=f"Official report was discovered but download/parse failed: {exc}",
                )
            )
    if not documents:
        documents.append(
            save_no_match_evidence(
                security.security_code,
                source,
                security,
                f"SSE periodic report query {begin.isoformat()} to {end.isoformat()}",
            )
        )
    return documents[:max_docs]
