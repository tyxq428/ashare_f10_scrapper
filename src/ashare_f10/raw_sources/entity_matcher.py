from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ashare_f10.fetch.security import parse_security
from ashare_f10.raw_sources.models import EntityMatch, SecurityEntity

_COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团股份有限公司",
    "集团有限公司",
    "公司",
    "co.,ltd.",
    "co., ltd.",
    "limited",
    "ltd.",
)


def standardize_security_code(value: str) -> str:
    raw = str(value).strip().upper()
    market_match = re.fullmatch(r"[01]\.(\d{6})", raw)
    if market_match:
        raw = market_match.group(1)
    prefix_match = re.fullmatch(r"(?:SH|SZ|BJ)(\d{6})", raw)
    if prefix_match:
        raw = prefix_match.group(1)
    suffix_match = re.fullmatch(r"(\d{6})\.(?:SH|SZ|BJ)", raw)
    if suffix_match:
        raw = suffix_match.group(1)
    return parse_security(raw).secucode


def normalize_company_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"[\s·•,，。.;；:：'\"()（）\[\]【】_-]+", "", text)
    for suffix in _COMPANY_SUFFIXES:
        compact = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", suffix.lower())
        if compact and text.endswith(compact):
            text = text[: -len(compact)]
            break
    return text


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""
    raw = value.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    domain = (urlparse(raw).hostname or "").lower()
    return domain.removeprefix("www.")


def _iter_records(combined: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group in combined.get("groups", []):
        for record in group.get("records", []):
            if isinstance(record, dict):
                records.append(record)
    return records


def _first(records: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for key in keys:
        for record in records:
            value = record.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def build_security_entity(
    f10_profile: dict[str, Any] | Path | None,
    raw_pack_overrides: dict[str, Any] | None = None,
    *,
    security_code: str | None = None,
) -> SecurityEntity:
    combined: dict[str, Any] = {}
    if isinstance(f10_profile, Path):
        if f10_profile.is_dir():
            f10_profile = f10_profile / "combined.json"
        if f10_profile.exists():
            import json

            combined = json.loads(f10_profile.read_text(encoding="utf-8"))
    elif isinstance(f10_profile, dict):
        combined = f10_profile

    metadata_security = combined.get("metadata", {}).get("security", {})
    code = security_code or metadata_security.get("code") or metadata_security.get("security_code")
    if not code:
        raise ValueError("security_code is required when F10 profile is unavailable")
    identity = parse_security(str(code))
    records = _iter_records(combined)
    name_abbr = _first(records, ("SECURITY_NAME_ABBR", "SECURITY_NAME", "ORG_NAME_ABBR")) or ""
    company_name = _first(records, ("ORG_NAME", "ORG_NAME_CN", "COMPANY_NAME")) or str(name_abbr)
    company_en = _first(records, ("ORG_NAME_EN", "ORG_NAME_ENG", "ENGLISH_NAME"))
    former = _first(records, ("FORMERNAME", "FORMER_NAME"))
    website = _first(records, ("ORG_WEB", "ORG_WEB_SITE", "OFFICIAL_WEBSITE", "WEB_SITE", "WEBSITE"))
    industry_values = [
        _first(records, ("CSRC_INDUSTRY_NAME",)),
        _first(records, ("BOARD_NAME_1LEVEL",)),
        _first(records, ("BOARD_NAME_2LEVEL",)),
        _first(records, ("BOARD_NAME_3LEVEL",)),
    ]
    brand_values = [
        str(name_abbr),
        _first(records, ("EXPAND_NAME_ABBR",)),
        _first(records, ("EXPAND_NAME_ABBRN",)),
    ]
    if website and not str(website).startswith(("http://", "https://")):
        website = f"https://{website}"
    entity = SecurityEntity(
        security_code=identity.code,
        secucode=identity.secucode,
        security_name_abbr=str(name_abbr or ""),
        company_full_name_cn=str(company_name or ""),
        company_full_name_en=str(company_en) if company_en else None,
        former_names=[item.strip() for item in re.split(r"[,，;；]", str(former or "")) if item.strip()],
        official_website=str(website) if website else None,
        listed_market={"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}.get(identity.exchange, "UNKNOWN"),
        industry_keywords=list(dict.fromkeys(str(item) for item in industry_values if item)),
        brand_keywords=list(dict.fromkeys(str(item) for item in brand_values if item)),
        entity_source="F10" if combined else "SECURITY_CODE_ONLY",
    )
    if raw_pack_overrides:
        entity = entity.model_copy(update=raw_pack_overrides)
    return entity


def match_entity(
    candidate: dict[str, Any] | str,
    security_entity: SecurityEntity,
    source_context: dict[str, Any] | None = None,
) -> EntityMatch:
    context = source_context or {}
    if isinstance(candidate, str):
        payload = {"name": candidate, "text": candidate}
    else:
        payload = candidate

    candidate_code = str(
        payload.get("security_code") or payload.get("SECURITY_CODE") or payload.get("code") or ""
    )
    candidate_secucode = str(payload.get("secucode") or payload.get("SECUCODE") or "")
    if candidate_code or candidate_secucode:
        try:
            normalized = standardize_security_code(candidate_secucode or candidate_code)
        except ValueError:
            normalized = ""
        if normalized == security_entity.secucode:
            return EntityMatch(
                matched_entity_id=security_entity.secucode,
                relation_to_listed_company="LISTED_PARENT",
                status="EXACT_ID_MATCH",
                confidence="very_high",
                matched_fields=["security_code"],
                candidate_name=str(payload.get("name") or payload.get("title") or ""),
                evidence=f"security code normalized to {normalized}",
            )

    credit_code = str(payload.get("unified_social_credit_code") or payload.get("credit_code") or "")
    if (
        credit_code
        and security_entity.unified_social_credit_code
        and credit_code == security_entity.unified_social_credit_code
    ):
        return EntityMatch(
            matched_entity_id=security_entity.secucode,
            relation_to_listed_company="LISTED_PARENT",
            status="EXACT_ID_MATCH",
            confidence="very_high",
            matched_fields=["unified_social_credit_code"],
            candidate_name=str(payload.get("name") or ""),
            evidence="unified social credit code exact match",
        )

    candidate_name = str(
        payload.get("company_name")
        or payload.get("name")
        or payload.get("applicant")
        or payload.get("supplier")
        or payload.get("title")
        or ""
    )
    normalized_candidate = normalize_company_name(candidate_name)
    normalized_full = normalize_company_name(security_entity.company_full_name_cn)
    if normalized_candidate and normalized_full and normalized_candidate == normalized_full:
        return EntityMatch(
            matched_entity_id=security_entity.secucode,
            relation_to_listed_company="LISTED_PARENT",
            status="EXACT_NAME_MATCH",
            confidence="high",
            matched_fields=["company_full_name_cn"],
            candidate_name=candidate_name,
            evidence="normalized legal entity name exact match",
        )

    for old_name in security_entity.former_names:
        if normalized_candidate and normalized_candidate == normalize_company_name(old_name):
            return EntityMatch(
                matched_entity_id=security_entity.secucode,
                relation_to_listed_company="LISTED_PARENT",
                status="HISTORICAL_NAME_MATCH",
                confidence="medium_high",
                matched_fields=["former_name"],
                candidate_name=candidate_name,
                evidence=f"historical name match: {old_name}",
            )

    candidate_url = str(payload.get("url") or payload.get("source_url") or "")
    candidate_domain = normalize_domain(candidate_url or context.get("source_url"))
    official_domain = normalize_domain(security_entity.official_website)
    if candidate_domain and official_domain and candidate_domain == official_domain:
        return EntityMatch(
            matched_entity_id=security_entity.secucode,
            relation_to_listed_company="BRAND",
            status="BRAND_DOMAIN_MATCH",
            confidence="medium",
            matched_fields=["official_domain"],
            candidate_name=candidate_name,
            evidence=f"official website domain match: {official_domain}",
        )

    text = str(payload.get("text") or payload.get("content") or candidate_name)
    if security_entity.security_name_abbr and security_entity.security_name_abbr in text:
        high_risk = bool(context.get("high_risk_name_match"))
        return EntityMatch(
            matched_entity_id=None if high_risk else security_entity.secucode,
            relation_to_listed_company="UNKNOWN" if high_risk else "BRAND",
            status="AMBIGUOUS_NAME_MATCH" if high_risk else "BRAND_DOMAIN_MATCH",
            confidence="low" if high_risk else "medium",
            matched_fields=["security_name_abbr"],
            candidate_name=candidate_name,
            evidence="short name occurrence requires a unique identifier"
            if high_risk
            else "brand/short name match",
        )

    return EntityMatch(
        matched_entity_id=None,
        relation_to_listed_company="UNKNOWN",
        status="NO_MATCH",
        confidence="none",
        matched_fields=[],
        candidate_name=candidate_name,
        evidence="no reliable entity identifier matched",
    )
