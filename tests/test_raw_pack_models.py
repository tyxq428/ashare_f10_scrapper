from __future__ import annotations

import pytest
from pydantic import ValidationError

from ashare_f10.raw_sources.models import SourceDocument, stable_document_id


def base_document(**updates):
    data = {
        "document_id": stable_document_id("688521", "SRC001", "doc"),
        "security_code": "688521",
        "pack_id": "P0_STATUTORY_CORE",
        "source_id": "SRC001",
        "source_tier": "T0_STATUTORY",
        "source_organization": "上海证券交易所",
        "source_domain": "sse.com.cn",
        "source_url": "https://www.sse.com.cn/doc",
        "status": "FACT_DIRECT",
        "access_status": "DOWNLOAD_OK",
    }
    data.update(updates)
    return data


def test_fact_direct_valid():
    doc = SourceDocument.model_validate(base_document())
    assert doc.status == "FACT_DIRECT"


def test_fact_direct_rejects_secondary_source():
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(base_document(source_tier="T4_SECONDARY"))


def test_no_match_requires_query_and_scope():
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(base_document(status="NO_MATCH", access_status="NO_EXACT_HIT"))
    doc = SourceDocument.model_validate(
        base_document(
            status="NO_MATCH",
            access_status="NO_EXACT_HIT",
            query="芯原股份",
            search_scope="HKEX exact issuer search",
            source_tier="T0_STATUTORY",
        )
    )
    assert doc.query == "芯原股份"


def test_permission_blocked_requires_minimum_action():
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(base_document(status="PERMISSION_BLOCKED", access_status="HTTP_403"))
    doc = SourceDocument.model_validate(
        base_document(
            status="PERMISSION_BLOCKED",
            access_status="HTTP_403",
            minimum_human_action="Use one compliant browser export",
        )
    )
    assert doc.minimum_human_action
