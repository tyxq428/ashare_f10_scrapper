from __future__ import annotations

import json

import pandas as pd

from ashare_f10.evidence import EvidenceGraphBuilder
from ashare_f10.research_mapping import ResearchMapper


def _official_fact() -> dict:
    return {
        "security_code": "688521",
        "source": "OFFICIAL_DISCLOSURE",
        "theme": "官方披露",
        "family": "OFFICIAL_DISCLOSURE",
        "dataset": "芯原股份2025年年度报告",
        "record_key": "official|2025|OPERATE_INCOME",
        "report_date": "2025-12-31",
        "event_date": None,
        "period_type": "FY",
        "data_semantics": "flow",
        "scope": "consolidated",
        "field_key": "OPERATE_INCOME",
        "field_name_cn": "营业收入",
        "value_num": 1_000_000_000.0,
        "value_text": "1000000000",
        "unit": "元",
        "normalized_unit": "元",
        "source_status": "FACT_DIRECT",
        "source_url": "https://sse.invalid/annual.pdf",
        "source_document": "芯原股份2025年年度报告",
        "document_id": "annual-current",
        "source_page": 80,
        "source_row": "营业收入 1,000,000,000.00",
        "available_at": "2026-03-20",
        "quality_flags": [],
    }


def _document(document_id: str, *, supersedes: str = "") -> dict:
    return {
        "document_id": document_id,
        "security_code": "688521",
        "source": "SSE",
        "source_tier": "T0_STATUTORY",
        "source_organization": "上海证券交易所",
        "source_url": f"https://sse.invalid/{document_id}.pdf",
        "document_title": f"芯原股份2025年年度报告-{document_id}",
        "document_type": "PERIODIC_REPORT",
        "publish_date": "2026-03-20",
        "report_date": "2025-12-31",
        "available_at": "2026-03-20",
        "version_label": "corrected" if supersedes else "original",
        "supersedes_document_id": supersedes,
        "sha256": "a" * 64,
        "status": "FACT_DIRECT",
        "access_status": "DOWNLOAD_OK",
        "parsed_text_path": "parsed/report.txt",
        "text_sha256": "b" * 64,
        "attachments": [
            {
                "attachment_id": "att-1",
                "source_url": "https://sse.invalid/attachment.pdf",
                "file_name": "attachment.pdf",
                "status": "DOWNLOAD_OK",
            }
        ],
    }


def test_observation_traces_to_source_fact_page_and_document() -> None:
    mapping = ResearchMapper(as_of_date="2026-03-31").map(pd.DataFrame([_official_fact()]))
    graph = EvidenceGraphBuilder().build(
        documents=[_document("annual-current")],
        source_facts=mapping.source_facts,
        canonical_observations=mapping.canonical_observations,
        lineage=mapping.lineage,
    )
    assert graph.quality["status"] == "PASS"
    assert graph.quality["dangling_edge_count"] == 0
    assert graph.quality["observation_lineage_coverage"] == 1.0
    assert graph.quality["observation_evidence_coverage"] == 1.0
    assert {"CANONICAL_OBSERVATION", "SOURCE_FACT", "DOCUMENT", "EVIDENCE_LOCATION"}.issubset(
        set(graph.nodes["node_type"])
    )

    observation_id = mapping.canonical_observations.iloc[0]["observation_id"]
    trace = graph.trace_observation(observation_id)
    assert observation_id in set(trace.nodes["node_id"])
    assert "DERIVED_FROM_DOCUMENT" in set(trace.edges["edge_type"])
    assert "LOCATED_AT" in set(trace.edges["edge_type"])
    location = trace.nodes[trace.nodes["node_type"] == "EVIDENCE_LOCATION"].iloc[0]
    attributes = json.loads(location["attributes_json"])
    assert attributes["page"] == 80
    assert "营业收入" in attributes["source_row"]


def test_document_version_attachment_and_parsed_text_edges_are_preserved() -> None:
    documents = [
        _document("annual-original"),
        _document("annual-corrected", supersedes="annual-original"),
    ]
    graph = EvidenceGraphBuilder().build(documents=documents)
    assert graph.quality["status"] == "PASS"
    assert "SUPERSEDES" in set(graph.edges["edge_type"])
    assert "ATTACHED_TO" in set(graph.edges["edge_type"])
    assert "PARSED_FROM" in set(graph.edges["edge_type"])
    assert "ATTACHMENT" in set(graph.nodes["node_type"])
    assert "PARSED_TEXT" in set(graph.nodes["node_type"])


def test_source_fact_without_document_record_creates_auditable_placeholder() -> None:
    fact = _official_fact()
    fact["document_id"] = ""
    fact["source_document"] = ""
    fact["source_url"] = "https://eastmoney.invalid/api"
    fact["source"] = "EASTMONEY"
    mapping = ResearchMapper().map(pd.DataFrame([fact]))
    graph = EvidenceGraphBuilder().build(
        source_facts=mapping.source_facts,
        canonical_observations=mapping.canonical_observations,
        lineage=mapping.lineage,
    )
    documents = graph.nodes[graph.nodes["node_type"] == "DOCUMENT"]
    assert len(documents) == 1
    attributes = json.loads(documents.iloc[0]["attributes_json"])
    assert attributes["placeholder"] is True
    assert graph.quality["observation_evidence_coverage"] == 1.0


def test_quarantined_lineage_uses_explicit_edge_type() -> None:
    fact = _official_fact()
    fact["source_status"] = "PARSE_SUSPECT"
    mapping = ResearchMapper().map(pd.DataFrame([fact]))
    graph = EvidenceGraphBuilder().build(
        documents=[_document("annual-current")],
        source_facts=mapping.source_facts,
        canonical_observations=mapping.canonical_observations,
        lineage=mapping.lineage,
    )
    assert "QUARANTINED_FOR" in set(graph.edges["edge_type"])
    assert graph.quality["status"] == "PASS"


def test_graph_ids_are_deterministic_and_unique() -> None:
    mapping = ResearchMapper().map(pd.DataFrame([_official_fact()]))
    builder = EvidenceGraphBuilder()
    first = builder.build(
        documents=[_document("annual-current")],
        source_facts=mapping.source_facts,
        canonical_observations=mapping.canonical_observations,
        lineage=mapping.lineage,
    )
    second = builder.build(
        documents=[_document("annual-current")],
        source_facts=mapping.source_facts,
        canonical_observations=mapping.canonical_observations,
        lineage=mapping.lineage,
    )
    assert list(first.nodes["node_id"]) == list(second.nodes["node_id"])
    assert list(first.edges["edge_id"]) == list(second.edges["edge_id"])
    assert first.quality["duplicate_node_id_count"] == 0
    assert first.quality["duplicate_edge_id_count"] == 0
