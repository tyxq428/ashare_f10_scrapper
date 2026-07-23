from __future__ import annotations

import json
import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from recovery_policy import classify  # noqa: E402


def test_context_budget_failure_does_not_retry_codex(
    tmp_path: Path,
) -> None:
    (tmp_path / "context-budget.json").write_text(
        json.dumps(
            {
                "status": "FAIL",
                "violations": ["TOTAL_ALLOWED_FILES_TOO_LARGE"],
            }
        ),
        encoding="utf-8",
    )
    jobs = {
        "jobs": [
            {
                "steps": [
                    {
                        "name": (
                            "Enforce context, runtime, Codex, scope, "
                            "gate and secret outcomes"
                        ),
                        "conclusion": "failure",
                    }
                ]
            }
        ]
    }

    decision = classify(
        source_workflow="Codex Task",
        source_run_id=123,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=jobs,
        artifact_root=tmp_path,
    )

    assert decision.action == "HUMAN_REQUIRED"
    assert decision.reason_code == "CONTEXT_BUDGET_EXCEEDED"
    assert decision.notification_type == "HUMAN_REQUIRED"
