from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.api.visual_execution_v2 import VisualJobRequest, visual_capabilities
from ashare_f10.api.visual_jobs_v2 import (
    DEFAULT_VISUAL_OPTIONS,
    OFFICIAL_VALIDATION_SCOPES,
    VisualJobManager,
    normalize_visual_options,
    official_max_periods,
    official_stage_outcome,
)
from ashare_f10.config import Settings
from ashare_f10.models import JobState


def test_visual_defaults_keep_optional_stages_disabled() -> None:
    request = VisualJobRequest(stock_code="688521")
    options = request.execution_options()
    assert options["include_raw_pack"] is False
    assert options["run_official_validation"] is False
    assert options["auto_retry_failed"] is True
    assert options["max_auto_retries"] == 2
    assert options["official_validation_scope"] == "full_history"
    assert options["official_max_periods"] is None
    assert DEFAULT_VISUAL_OPTIONS["raw_pack_packs"] == "default"


def test_visual_option_normalization_bounds_values_and_scope() -> None:
    options = normalize_visual_options(
        {
            "workers": 999,
            "max_auto_retries": 99,
            "retry_backoff_seconds": -1,
            "raw_pack_max_docs": 99999,
            "official_annual_year": 1900,
            "official_quarter_year": 2200,
            "official_validation_scope": "not-a-real-scope",
        }
    )
    assert options["workers"] == 32
    assert options["max_auto_retries"] == 5
    assert options["retry_backoff_seconds"] == 0
    assert options["raw_pack_max_docs"] == 5000
    assert options["official_annual_year"] == 2000
    assert options["official_quarter_year"] == 2100
    assert options["official_validation_scope"] == "full_history"
    assert options["official_max_periods"] is None
    assert official_max_periods("latest") == 2
    assert official_max_periods("recent_3y") == 12
    assert official_max_periods("recent_5y") == 20
    assert official_max_periods("full_history") is None


def test_visual_capabilities_expose_full_history_as_default() -> None:
    payload = visual_capabilities()
    presets = {item["id"]: item for item in payload["presets"]}
    scopes = {item["value"]: item for item in payload["official_validation_scopes"]}
    assert presets["full_research"]["include_raw_pack"] is True
    assert presets["full_research"]["run_official_validation"] is True
    assert payload["defaults"]["include_raw_pack"] is False
    assert payload["defaults"]["official_validation_scope"] == "full_history"
    assert scopes["full_history"]["max_periods"] is None
    assert "上市以来" in scopes["full_history"]["label"]
    assert set(scopes) == set(OFFICIAL_VALIDATION_SCOPES)


def test_visual_sidecar_is_backward_compatible(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    manager = VisualJobManager(settings)
    output_dir = tmp_path / "data" / "688521" / "dummy-job"
    state = JobState(
        job_id="dummy-job",
        stock_code="688521",
        status="COMPLETED",
        created_at_utc="2026-07-22T00:00:00Z",
        updated_at_utc="2026-07-22T00:01:00Z",
        output_dir=str(output_dir),
        total_groups=113,
        completed_groups=113,
        successful_groups=113,
    )
    payload = manager.visual_payload(state)
    assert payload["visual"]["stage_status"]["f10"] == "COMPLETED"
    assert payload["visual"]["stage_status"]["raw_pack"] == "NOT_REQUESTED"
    manager._write_sidecar(
        state,
        {
            "options": {**DEFAULT_VISUAL_OPTIONS, "include_raw_pack": True},
            "stage_status": {"f10": "COMPLETED", "raw_pack": "PENDING"},
        },
    )
    saved = json.loads((output_dir / "visual-execution.json").read_text(encoding="utf-8"))
    assert saved["options"]["include_raw_pack"] is True
    assert saved["stage_status"]["raw_pack"] == "PENDING"
    assert saved["heartbeat_at_utc"]


def test_legacy_artifacts_infer_optional_stage_completion(tmp_path: Path) -> None:
    manager = VisualJobManager(Settings(data_dir=tmp_path / "data"))
    state = JobState(
        job_id="legacy-job",
        stock_code="688521",
        status="COMPLETED",
        created_at_utc="2026-07-22T00:00:00Z",
        updated_at_utc="2026-07-22T00:01:00Z",
        output_dir=str(tmp_path / "legacy"),
        total_groups=113,
        completed_groups=113,
        successful_groups=113,
        artifacts={
            "json": "/tmp/f10.json",
            "raw_pack_excel": "/tmp/raw.xlsx",
            "official_summary_json": "/tmp/summary.json",
        },
    )
    visual = manager.visual_payload(state)["visual"]
    assert visual["stage_status"]["f10"] == "COMPLETED"
    assert visual["stage_status"]["raw_pack"] == "COMPLETED"
    assert visual["stage_status"]["official_validation"] == "COMPLETED"


def test_official_source_conflict_is_completed_with_review() -> None:
    outcome = official_stage_outcome(
        {
            "acceptance_status": "FAIL_SOURCE_CONFLICT",
            "manual_review_required": True,
            "true_conflict_count": 1,
            "official_fact_count": 2975,
            "comparison_count": 6191,
            "official_source_status": {"document_count": 23},
        },
        "full_history",
    )
    assert outcome["stored_status"] == "COMPLETED"
    assert outcome["display_status"] == "COMPLETED_WITH_REVIEW"
    assert outcome["warning_delta"] == 1
    assert "23份官方报告" in outcome["message"]
    assert "需要复核" in outcome["message"]
def test_official_coverage_gap_is_completed_with_review() -> None:
    outcome = official_stage_outcome(
        {
  "acceptance_status": "PASS_WITH_COVERAGE_GAPS",
  "manual_review_required": False,
  "true_conflict_count": 0,
  "official_fact_count": 1200,
  "comparison_count": 4000,
  "official_source_status": {"document_count": 18},
        },
        "full_history",
    )
    assert outcome["stored_status"] == "COMPLETED"
    assert outcome["display_status"] == "COMPLETED_WITH_REVIEW"
    assert outcome["warning_delta"] == 1
    assert "覆盖缺口" in outcome["message"]


def test_partial_official_source_is_completed_with_review() -> None:
    outcome = official_stage_outcome(
        {
  "acceptance_status": "PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE",
  "manual_review_required": False,
  "true_conflict_count": 0,
  "official_fact_count": 0,
  "comparison_count": 0,
  "official_source_status": {"document_count": 0},
        },
        "latest",
    )
    assert outcome["stored_status"] == "COMPLETED"
    assert outcome["display_status"] == "COMPLETED_WITH_REVIEW"
    assert outcome["warning_delta"] == 1
    assert "官方来源部分不可用" in outcome["message"]


# Post-hotfix validation marker for main 434f31baca281e9eb4e38e9f2e1c3151cbee5c56.
