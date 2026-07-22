from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.raw_sources.entity_matcher import (
    build_security_entity,
    match_entity,
    normalize_company_name,
    standardize_security_code,
)

FIXTURES = Path(__file__).parent / "fixtures" / "raw_pack"


def entity():
    combined = {
        "metadata": {"security": {"code": "688521"}},
        "groups": [
            {
                "records": [
                    {
                        "SECURITY_CODE": "688521",
                        "SECURITY_NAME_ABBR": "芯原股份",
                        "ORG_NAME": "芯原微电子(上海)股份有限公司",
                        "ORG_NAME_EN": "VeriSilicon Microelectronics (Shanghai) Co., Ltd.",
                        "ORG_WEB": "www.verisilicon.com",
                        "BOARD_NAME_2LEVEL": "半导体",
                    }
                ]
            }
        ],
    }
    return build_security_entity(combined)


def test_security_code_variants():
    variants = json.loads((FIXTURES / "security_code_variants.json").read_text())
    assert {standardize_security_code(value) for value in variants} == {"688521.SH"}


def test_build_entity_from_f10_profile():
    value = entity()
    assert value.company_full_name_cn.startswith("芯原微电子")
    assert value.official_website == "https://www.verisilicon.com"
    assert value.listed_market == "SSE"


def test_exact_name_and_domain_matches():
    value = entity()
    exact = match_entity({"name": "芯原微电子（上海）股份有限公司"}, value)
    assert exact.status == "EXACT_NAME_MATCH" and exact.confidence == "high"
    domain = match_entity({"url": "https://www.verisilicon.com/cn/AboutVeriSilicon"}, value)
    assert domain.status == "BRAND_DOMAIN_MATCH"


def test_short_name_rejected_for_high_risk_source():
    value = entity()
    match = match_entity("芯原股份", value, {"high_risk_name_match": True})
    assert match.status == "AMBIGUOUS_NAME_MATCH"
    assert match.matched_entity_id is None


def test_company_name_normalization():
    assert normalize_company_name("芯原微电子（上海）股份有限公司") == normalize_company_name(
        "芯原微电子(上海)股份有限公司"
    )
