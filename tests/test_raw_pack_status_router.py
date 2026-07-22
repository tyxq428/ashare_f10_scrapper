from __future__ import annotations

import pytest

from ashare_f10.raw_sources.models import DownloadResult, RawSource, SecurityEntity
from ashare_f10.raw_sources.status_router import save_no_match_evidence, save_permission_block


def source():
    return RawSource(
        source_id="SRC016",
        name="国家企业信用信息公示系统",
        pack_id="P1_ENTITY_RISK_CORE",
        source_tier="T1_GOV_OFFICIAL",
        official_organization="市场监管总局",
        base_url="https://www.gsxt.gov.cn/index.html",
        expected_domains=["gsxt.gov.cn"],
        default_policy="INCLUDE_CORE",
        priority="P1",
    )


def entity():
    return SecurityEntity(
        security_code="688521",
        secucode="688521.SH",
        company_full_name_cn="芯原微电子（上海）股份有限公司",
        listed_market="SSE",
    )


def test_save_no_match_preserves_query_without_fact_value():
    doc = save_no_match_evidence("芯原微电子", source(), entity(), "exact legal-name search")
    assert doc.status == "NO_MATCH"
    assert doc.query == "芯原微电子"
    assert doc.file_size_bytes is None


def test_permission_blocked_requires_action_and_does_not_retry():
    result = DownloadResult(
        url=source().base_url,
        final_url=source().base_url,
        status_code=403,
        access_status="HTTP_403",
        error="Forbidden",
        attempts=1,
    )
    doc = save_permission_block(
        result,
        source(),
        entity(),
        "芯原微电子",
        "Use one browser export",
        "Unified social credit code remains unresolved",
    )
    assert doc.status == "PERMISSION_BLOCKED"
    assert doc.minimum_human_action == "Use one browser export"
    assert result.attempts == 1


def test_no_match_cannot_be_given_a_file_size():
    doc = save_no_match_evidence("芯原", source(), entity(), "scope")
    data = doc.model_dump()
    data["file_size_bytes"] = 10
    with pytest.raises(ValueError):
        type(doc).model_validate(data)
