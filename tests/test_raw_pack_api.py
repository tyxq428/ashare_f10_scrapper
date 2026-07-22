from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ashare_f10.api.raw_pack import router
from ashare_f10.config import settings
from ashare_f10.raw_sources.models import SourceDocument, stable_document_id


def _prepare_data(tmp_path: Path) -> tuple[str, Path]:
    stock_code = "688521"
    f10_dir = tmp_path / stock_code / "run-1"
    raw_dir = f10_dir / "raw_pack" / stock_code / "20260721T000000Z"
    index_dir = raw_dir / "source_index"
    source_dir = raw_dir / "raw_sources" / "P0_STATUTORY_CORE" / "SRC001"
    parsed_dir = raw_dir / "parsed_sources" / "P0_STATUTORY_CORE" / "SRC001"
    index_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)
    parsed_dir.mkdir(parents=True)

    source_file = source_dir / "announcement.html"
    source_file.write_text("<html>688521 芯原股份 official</html>", encoding="utf-8")
    parsed_file = parsed_dir / "document.txt"
    parsed_file.write_text("芯原股份 688521 上市公告", encoding="utf-8")

    direct = SourceDocument(
        document_id=stable_document_id(stock_code, "SRC001", "direct"),
        security_code=stock_code,
        matched_entity_id="688521.SH",
        relation_to_listed_company="LISTED_PARENT",
        entity_match_status="EXACT_ID_MATCH",
        entity_match_confidence="very_high",
        pack_id="P0_STATUTORY_CORE",
        source_id="SRC001",
        source_tier="T0_STATUTORY",
        source_organization="上海证券交易所",
        source_domain="sse.com.cn",
        source_url="https://www.sse.com.cn/example",
        document_title="芯原股份上市公告",
        document_type="ANNOUNCEMENT",
        status="FACT_DIRECT",
        access_status="DOWNLOAD_OK",
        raw_original_binary_saved=True,
        parsed_text_saved=True,
        original_file_path=str(source_file),
        parsed_text_path=str(parsed_file),
        content_type="text/html",
        file_size_bytes=source_file.stat().st_size,
        sha256="a" * 64,
        text_sha256="b" * 64,
    )
    blocked = SourceDocument(
        document_id=stable_document_id(stock_code, "SRC016", "blocked"),
        security_code=stock_code,
        pack_id="P1_ENTITY_RISK_CORE",
        source_id="SRC016",
        source_tier="T1_GOV_OFFICIAL",
        source_organization="市场监管总局",
        source_domain="gsxt.gov.cn",
        source_url="https://www.gsxt.gov.cn/index.html",
        document_title="国家企业信用信息公示系统 access blocked",
        status="PERMISSION_BLOCKED",
        access_status="HTTP_403",
        query="芯原微电子（上海）股份有限公司",
        search_scope="official registry",
        minimum_human_action="Use one compliant browser export",
    )
    (index_dir / "source_documents.jsonl").write_text(
        "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in (direct, blocked))
        + "\n",
        encoding="utf-8",
    )
    latest_pointer = f10_dir / "raw_pack" / stock_code / "latest.json"
    latest_pointer.parent.mkdir(parents=True, exist_ok=True)
    latest_pointer.write_text(
        json.dumps(
            {
                "output_dir": str(raw_dir),
                "source_documents_jsonl": str(index_dir / "source_documents.jsonl"),
                "quality_report_json": str(raw_dir / "quality" / "raw_pack_quality.json"),
            }
        ),
        encoding="utf-8",
    )
    stock_pointer = tmp_path / stock_code / "latest.json"
    stock_pointer.write_text(json.dumps({"output_dir": str(f10_dir), "artifacts": {}}), encoding="utf-8")
    return stock_code, direct.document_id


def test_raw_pack_evidence_api(tmp_path: Path, monkeypatch) -> None:
    stock_code, document_id = _prepare_data(tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    stats = client.get("/api/raw-pack/evidence/stats", params={"stock_code": stock_code})
    assert stats.status_code == 200
    assert stats.json()["status_counts"] == {"FACT_DIRECT": 1, "PERMISSION_BLOCKED": 1}

    search = client.get(
        "/api/raw-pack/evidence/search",
        params={"stock_code": stock_code, "q": "上市公告", "status": "FACT_DIRECT"},
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1

    detail = client.get(f"/api/raw-pack/documents/{document_id}", params={"stock_code": stock_code})
    assert detail.status_code == 200
    assert "688521" in detail.json()["text"]
    assert detail.json()["document"]["sha256"] == "a" * 64

    blocked = client.get("/api/raw-pack/blocked", params={"stock_code": stock_code})
    assert blocked.status_code == 200
    assert blocked.json()[0]["minimum_human_action"]

    download = client.get(
        f"/api/raw-pack/documents/{document_id}/download", params={"stock_code": stock_code}
    )
    assert download.status_code == 200 and download.content
