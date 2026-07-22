from __future__ import annotations

from ashare_f10.raw_sources.models import SecurityEntity
from ashare_f10.raw_sources.source_manifest import load_raw_source_manifest, manifest_summary, select_sources


def entity():
    return SecurityEntity(
        security_code="688521",
        secucode="688521.SH",
        security_name_abbr="芯原股份",
        company_full_name_cn="芯原微电子（上海）股份有限公司",
        listed_market="SSE",
    )


def test_manifest_loads_full_candidate_universe():
    summary = manifest_summary()
    assert summary["source_count"] == 67
    assert summary["pack_count"] == 7
    assert "P0_STATUTORY_CORE" in summary["packs"]


def test_select_sources_respects_flag_and_default_packs():
    assert select_sources(entity(), False) == []
    selected = select_sources(entity(), True, "default")
    assert selected
    assert all(item.implemented and item.default_enabled for item in selected)
    assert any(item.collector == "sse_disclosure" for item in selected)


def test_all_pack_selection_only_returns_implemented_sources():
    selected = select_sources(entity(), True, "all")
    manifest = load_raw_source_manifest()
    assert len(selected) == sum(item.implemented for item in manifest.sources)
