from __future__ import annotations

import json
import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from recovery_policy import classify  # noqa: E402


def failed_jobs(step_name: str) -> dict[str, object]:
    return {
        "jobs": [
            {
                "name": "job",
                "steps": [
                    {"name": "Set up job", "conclusion": "success"},
                    {"name": step_name, "conclusion": "failure"},
                ],
            }
        ]
    }


def write_codex_result(
    root: Path,
    value: dict[str, object],
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "codex-result.json").write_text(
        json.dumps(value),
        encoding="utf-8",
    )


def test_blocked_codex_result_is_never_retried(
    tmp_path: Path,
) -> None:
    write_codex_result(
        tmp_path,
        {
            "status": "BLOCKED",
            "tests_passed": False,
            "changed_files": [],
            "blocking_reason": (
                "approved scope excludes the failing file"
            ),
        },
    )
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=1,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs(
            "Enforce context, runtime, Codex, scope, gate and secret outcomes"
        ),
        artifact_root=tmp_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_DECLARED_BLOCKED"
    assert decision.notification_type == "INTERRUPTED"


def test_codex_failure_without_result_has_no_identical_rerun(
    tmp_path: Path,
) -> None:
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=2,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs(
            "Run one Codex Thin Worker session"
        ),
        artifact_root=tmp_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_EXECUTION_FAILED_NO_RETRY"


def test_unverified_codex_success_is_not_retried(
    tmp_path: Path,
) -> None:
    write_codex_result(
        tmp_path,
        {
            "status": "SUCCESS",
            "tests_passed": False,
            "changed_files": ["scripts/example.py"],
        },
    )
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=3,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs(
            "Run trusted targeted gate"
        ),
        artifact_root=tmp_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_RESULT_UNVERIFIED"


def test_state_consistency_without_descriptor_does_not_synthesize_scope(
    tmp_path: Path,
) -> None:
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=4,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs(
            "Validate Devflow workflows, docs and tests"
        ),
        artifact_root=tmp_path,
        task_file=tmp_path / "missing-task.json",
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "STATE_REPAIR_SCOPE_UNAVAILABLE"


def test_verified_infrastructure_failure_still_retries_silently(
    tmp_path: Path,
) -> None:
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=5,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
        artifact_root=tmp_path,
    )
    assert decision.action == "RETRY"
    assert decision.notification_type is None
