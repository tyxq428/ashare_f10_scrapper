from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
from fastapi.testclient import TestClient

from ashare_f10.api import research_pack as research_api
from ashare_f10.api.app_with_raw_pack import app


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_pack(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    run_dir = data_dir / "688521" / "job-1"
    output_dir = run_dir / "research_pack" / "thin_slice"
    exports = output_dir / "exports"
    quality_dir = output_dir / "quality"
    exports.mkdir(parents=True)
    quality_dir.mkdir(parents=True)

    database = exports / "688521_research_pack.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            """
            CREATE TABLE canonical_observations AS SELECT * FROM (VALUES
              ('obs_1','688521','operating_revenue','营业收入','profit_quality',
               '2025-12-31',NULL,'FY','flow','consolidated',100.0,NULL,'元',
               'SOURCE_CONFLICT','medium','sf_1',2,1,1,'2026-07-22'),
              ('obs_2','688521','research_expense','研发费用','research_and_development',
               '2025-12-31',NULL,'FY','flow','consolidated',20.0,NULL,'元',
               'VERIFIED_MULTI_SOURCE','high','sf_2',2,2,0,'2026-07-22')
            ) AS t(
              observation_id,security_code,metric_id,metric_name_cn,research_module,
              report_date,event_date,period_type,data_semantics,scope,value_num,value_text,unit,
              status,confidence,selected_source_fact_id,source_count,usable_source_count,
              conflict_count,as_of_date
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE source_facts AS SELECT * FROM (VALUES
              ('sf_1','688521','operating_revenue','营业收入','profit_quality',TRUE,
               'OFFICIAL_DISCLOSURE',100,'PARSE_SUSPECT','2025-12-31',NULL,'FY','flow',
               'consolidated','OPERATE_INCOME','营业收入','OFFICIAL_DISCLOSURE','report','r1',
               100.0,100.0,NULL,'元','元','2026-04-01','https://example.test/report.pdf',
               '2025年年度报告','doc_1',88,'营业收入 100','[]',TRUE),
              ('sf_2','688521','research_expense','研发费用','research_and_development',TRUE,
               'EASTMONEY',60,'FACT_DIRECT','2025-12-31',NULL,'FY','flow','consolidated',
               'RESEARCH_EXPENSE','研发费用','RPT_F10_BUSINESS_RDEXPENSE','rd','r2',
               20.0,20.0,NULL,'元','元','2026-03-20','https://example.test/eastmoney',
               '', '',NULL,'','[]',FALSE)
            ) AS t(
              source_fact_id,security_code,metric_id,metric_name_cn,research_module,
              explicitly_mapped,source_name,source_priority,source_status,report_date,event_date,
              period_type,data_semantics,scope,field_key,field_name_cn,family,dataset,record_key,
              value_num,normalized_value_num,value_text,unit,normalized_unit,available_at,
              source_url,source_document,document_id,source_page,source_row,quality_flags,
              is_quarantined
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE fact_lineage AS SELECT * FROM (VALUES
              ('lin_1','obs_1','sf_1','CONFLICTING',100,'OFFICIAL_DISCLOSURE',
               'PARSE_SUSPECT','official candidate quarantined'),
              ('lin_2','obs_2','sf_2','SELECTED',60,'EASTMONEY','FACT_DIRECT','selected')
            ) AS t(lineage_id,observation_id,source_fact_id,role,source_priority,
                   source_name,source_status,selection_reason)
            """
        )
        connection.execute(
            """
            CREATE TABLE evidence_nodes AS SELECT * FROM (VALUES
              ('obs_1','CANONICAL_OBSERVATION','688521','营业收入','{}'),
              ('sf_1','SOURCE_FACT','688521','营业收入','{}'),
              ('doc_1','DOCUMENT','688521','2025年年度报告','{"document_title":"2025年年度报告","report_date":"2025-12-31","available_at":"2026-04-01","version_label":"更正版","source_url":"https://example.test/report.pdf"}'),
              ('doc_0','DOCUMENT','688521','2025年年度报告原版','{"document_title":"2025年年度报告原版","report_date":"2025-12-31","available_at":"2026-03-20","version_label":"原版"}'),
              ('loc_1','EVIDENCE_LOCATION','688521','doc_1 p.88',
               '{"document_id":"doc_1","page":88,"source_row":"营业收入 100"}')
            ) AS t(node_id,node_type,security_code,label,attributes_json)
            """
        )
        connection.execute(
            """
            CREATE TABLE evidence_edges AS SELECT * FROM (VALUES
              ('edge_1','obs_1','sf_1','CONFLICTS_WITH','{}'),
              ('edge_2','sf_1','doc_1','DERIVED_FROM_DOCUMENT','{}'),
              ('edge_3','sf_1','loc_1','LOCATED_AT','{}'),
              ('edge_4','loc_1','doc_1','PART_OF_DOCUMENT','{}'),
              ('edge_5','doc_1','doc_0','SUPERSEDES','{}')
            ) AS t(edge_id,from_node_id,to_node_id,edge_type,attributes_json)
            """
        )
        connection.execute(
            """
            CREATE TABLE coverage_gaps AS SELECT * FROM (VALUES
              ('operating_revenue','PARSE_SUSPECT','需要人工复核')
            ) AS t(metric_id,status,notes)
            """
        )
    finally:
        connection.close()

    summary_path = output_dir / "summary.json"
    quality_path = quality_dir / "research_pack_quality.json"
    manifest_path = output_dir / "manifest.json"
    checkpoint_path = output_dir / "checkpoint.json"
    package_json = exports / "688521_research_pack.json"
    package_excel = exports / "688521_research_pack.xlsx"
    for path, payload in (
        (
            summary_path,
            {
                "schema_version": "1.0.0",
                "security_code": "688521",
                "as_of_date": "2026-07-22",
                "generated_at_utc": "2026-07-22T00:00:00Z",
                "mapping_coverage": {"mapping_coverage": 1.0, "source_conflict_count": 1},
                "evidence_quality": {"observation_evidence_coverage": 0.5},
            },
        ),
        (quality_path, {"status": "PASS", "failures": []}),
        (manifest_path, {"schema_version": "1.0.0"}),
        (checkpoint_path, {"status": "COMPLETED"}),
        (package_json, {"metadata": {"security_code": "688521"}}),
    ):
        _write_json(path, payload)
    package_excel.write_bytes(b"xlsx-placeholder")

    cross_summary = run_dir / "cross_validation" / "thin_slice" / "cross_validation_summary.json"
    _write_json(
        cross_summary,
        {
            "classification_coverage": 1.0,
            "comparison_coverage": 0.8,
            "comparison_accuracy": 0.95,
            "evidence_completeness": 0.9,
            "suspicious_extraction_rate": 0.01,
            "unresolved_rate": 0.02,
            "true_conflict_count": 1,
            "acceptance_status": "FAIL_SOURCE_CONFLICT",
        },
    )
    artifacts = {
        "output_dir": str(output_dir),
        "manifest_json": str(manifest_path),
        "summary_json": str(summary_path),
        "package_json": str(package_json),
        "package_excel": str(package_excel),
        "package_duckdb": str(database),
        "quality_json": str(quality_path),
        "checkpoint_json": str(checkpoint_path),
    }
    _write_json(
        run_dir / "research_pack" / "latest.json",
        {
            "stock_code": "688521",
            "mode": "thin-slice",
            "as_of_date": "2026-07-22",
            "run_dir": str(run_dir),
            "output_dir": str(output_dir),
            "cross_validation_summary": str(cross_summary),
            "artifacts": artifacts,
        },
    )
    _write_json(data_dir / "688521" / "latest.json", {"output_dir": str(run_dir)})
    monkeypatch.setattr(research_api.settings, "data_dir", data_dir)
    return run_dir, output_dir


def test_research_pack_capabilities_expose_modes() -> None:
    payload = research_api.research_pack_capabilities()
    assert {item["id"] for item in payload["modes"]} == {"thin-slice", "research-full"}
    assert "comparison_accuracy" in payload["quality_dimensions"]
    assert "parse_suspect" in payload["issue_filters"]


def test_research_pack_latest_fact_filters_and_evidence(tmp_path: Path, monkeypatch) -> None:
    _build_pack(tmp_path, monkeypatch)
    client = TestClient(app)

    latest = client.get("/api/research-pack/stocks/688521/latest")
    assert latest.status_code == 200
    dimensions = latest.json()["quality_dimensions"]
    assert dimensions["classification_coverage"] == 1.0
    assert dimensions["comparison_coverage"] == 0.8
    assert dimensions["comparison_accuracy"] == 0.95
    assert dimensions["evidence_completeness"] == 0.9

    suspect = client.get(
        "/api/research-pack/stocks/688521/facts",
        params={"issue": "parse_suspect"},
    )
    assert suspect.status_code == 200
    assert suspect.json()["total"] == 1
    assert suspect.json()["rows"][0]["observation_id"] == "obs_1"

    conflicts = client.get(
        "/api/research-pack/stocks/688521/facts",
        params={"issue": "source_conflict"},
    )
    assert conflicts.status_code == 200
    assert conflicts.json()["total"] == 1

    evidence = client.get("/api/research-pack/stocks/688521/facts/obs_1/evidence")
    assert evidence.status_code == 200
    payload = evidence.json()
    assert payload["observation"]["metric_id"] == "operating_revenue"
    assert any(node["node_type"] == "DOCUMENT" for node in payload["nodes"])
    assert any(node["node_type"] == "EVIDENCE_LOCATION" for node in payload["nodes"])

    versions = client.get("/api/research-pack/stocks/688521/versions")
    assert versions.status_code == 200
    assert versions.json()["as_of_date"] == "2026-07-22"
    assert versions.json()["supersedes_edges"][0]["to_node_id"] == "doc_0"

    download = client.get("/api/research-pack/stocks/688521/download/summary")
    assert download.status_code == 200
    assert len(download.content) > 20


def test_research_pack_mode_controls_cross_validation_scope(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    calls: list[int | None] = []

    monkeypatch.setattr(research_api, "_latest_f10_output", lambda _code: run_dir)

    def fake_cross_validation(
        stock_code: str,
        input_dir: Path,
        output_dir: Path,
        max_periods: int | None = None,
        as_of_date: str | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        assert stock_code == "002352"
        assert input_dir == run_dir
        assert as_of_date == "2026-07-22"
        calls.append(max_periods)
        _write_json(output_dir / "cross_validation_summary.json", {"acceptance_status": "PASS"})
        return {"acceptance_status": "PASS", "manual_review_required": False}

    def fake_pack(
        stock_code: str,
        input_dir: Path,
        output_dir: Path,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        assert stock_code == "002352"
        assert input_dir == run_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name, relative in {
            "output_dir": ".",
            "manifest_json": "manifest.json",
            "summary_json": "summary.json",
            "package_json": "exports/package.json",
            "package_excel": "exports/package.xlsx",
            "package_duckdb": "exports/package.duckdb",
            "quality_json": "quality/research_pack_quality.json",
            "checkpoint_json": "checkpoint.json",
        }.items():
            path = output_dir if name == "output_dir" else output_dir / relative
            if name != "output_dir":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            artifacts[name] = str(path)
        return {
            "status": "COMPLETED",
            "cache_hit": False,
            "summary": {"as_of_date": "2026-07-22"},
            "artifacts": artifacts,
        }

    monkeypatch.setattr(research_api, "run_full_cross_validation", fake_cross_validation)
    monkeypatch.setattr(research_api, "run_research_pack", fake_pack)
    research_api._JOBS["job"] = {"job_id": "job", "created_at_utc": research_api.utc_now()}
    request = research_api.ResearchPackJobRequest(
        stock_code="002352",
        mode="thin-slice",
        as_of_date="2026-07-22",
    )
    research_api._run_job("job", request)
    assert calls == [2]
    assert research_api._JOBS["job"]["status"] == "COMPLETED"
    pointer = json.loads((run_dir / "research_pack" / "latest.json").read_text(encoding="utf-8"))
    assert pointer["mode"] == "thin-slice"
