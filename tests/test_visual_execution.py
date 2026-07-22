from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.api.visual_execution import VisualJobRequest, visual_capabilities
from ashare_f10.api.visual_jobs import DEFAULT_VISUAL_OPTIONS, VisualJobManager, normalize_visual_options
from ashare_f10.config import Settings
from ashare_f10.models import JobState


def test_visual_defaults_keep_optional_stages_disabled() -> None:
    request = VisualJobRequest(stock_code="688521")
    options = request.execution_options()
    assert options["include_raw_pack"] is False
    assert options["run_official_validation"] is False
    assert options["auto_retry_failed"] is True
    assert options["max_auto_retries"] == 2
    assert DEFAULT_VISUAL_OPTIONS["raw_pack_packs"] == "default"


def test_visual_option_normalization_bounds_values() -> None:
    options = normalize_visual_options(
        {
            "workers": 999,
            "max_auto_retries": 99,
            "retry_backoff_seconds": -1,
            "raw_pack_max_docs": 99999,
            "official_annual_year": 1900,
            "official_quarter_year": 2200,
        }
    )
    assert options["workers"] == 32
    assert options["max_auto_retries"] == 5
    assert options["retry_backoff_seconds"] == 0
    assert options["raw_pack_max_docs"] == 5000
    assert options["official_annual_year"] == 2000
    assert options["official_quarter_year"] == 2100


def test_visual_capabilities_expose_complete_research_preset() -> None:
    payload = visual_capabilities()
    presets = {item["id"]: item for item in payload["presets"]}
    assert presets["full_research"]["include_raw_pack"] is True
    assert presets["full_research"]["run_official_validation"] is True
    assert payload["defaults"]["include_raw_pack"] is False


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
