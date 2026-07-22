from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.api.visual_jobs_v2 import (
    DEFAULT_VISUAL_OPTIONS,
    OFFICIAL_VALIDATION_SCOPES,
    VisualJobManager as VisualJobManagerV2,
    normalize_visual_options,
    official_max_periods,
    official_stage_outcome,
)
from ashare_f10.config import Settings
from ashare_f10.models import JobState


class VisualJobManager(VisualJobManagerV2):
    """Production visual manager with final parallel-artifact reconciliation."""

    def _merge_artifact_manifest(self, state: JobState) -> None:
        path = Path(state.output_dir) / "artifacts.json"
        with self._visual_lock:
            payload: dict = {}
            if path.exists():
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(existing, dict):
                        payload.update(existing)
                except Exception:  # noqa: BLE001
                    pass
            payload.update(
                {
                    key: value
                    for key, value in (state.artifacts or {}).items()
                    if isinstance(value, str) and value
                }
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)

    def _run_optional_stages(self, state: JobState, job_settings: Settings) -> int:
        warnings = super()._run_optional_stages(state, job_settings)
        self._merge_artifact_manifest(state)
        return warnings


__all__ = [
    "DEFAULT_VISUAL_OPTIONS",
    "OFFICIAL_VALIDATION_SCOPES",
    "VisualJobManager",
    "normalize_visual_options",
    "official_max_periods",
    "official_stage_outcome",
]
