from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.api.visual_jobs_runtime import VisualJobManager
from ashare_f10.config import Settings
from ashare_f10.models import JobState


def test_optional_stage_artifacts_are_atomically_reconciled(tmp_path: Path) -> None:
    manager = VisualJobManager(Settings(data_dir=tmp_path / "data"))
    output_dir = tmp_path / "data" / "688521" / "combined-job"
    output_dir.mkdir(parents=True)
    (output_dir / "artifacts.json").write_text(
        json.dumps({"json": "f10.json", "comparison_json": "comparison.json"}),
        encoding="utf-8",
    )
    state = JobState(
        job_id="combined-job",
        stock_code="688521",
        status="COMPLETED",
        created_at_utc="2026-07-22T00:00:00Z",
        updated_at_utc="2026-07-22T00:01:00Z",
        output_dir=str(output_dir),
        artifacts={
            "json": "f10.json",
            "raw_pack_excel": "raw-pack.xlsx",
            "official_summary_json": "cross-validation-summary.json",
        },
    )

    manager._merge_artifact_manifest(state)

    payload = json.loads((output_dir / "artifacts.json").read_text(encoding="utf-8"))
    assert payload["json"] == "f10.json"
    assert payload["comparison_json"] == "comparison.json"
    assert payload["raw_pack_excel"] == "raw-pack.xlsx"
    assert payload["official_summary_json"] == "cross-validation-summary.json"
