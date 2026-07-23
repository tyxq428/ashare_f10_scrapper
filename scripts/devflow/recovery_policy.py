from __future__ import annotations

"""Stable compatibility entry point for the versioned recovery policy.

Production workflows always provide an artifact root. A narrow legacy adapter
keeps historical unit callers readable without re-enabling identical Codex
reruns in the actual Auto Recovery workflow.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

from recovery_policy_v2 import (
    RecoveryDecision,
    classify as _classify_v2,
    main,
)


def classify(
    *,
    source_workflow: str,
    source_run_id: int,
    conclusion: str,
    run_attempt: int,
    jobs_payload: dict[str, Any],
    artifact_root: Path | None = None,
    task_file: Path | None = None,
    infrastructure_retry_limit: int = 3,
) -> RecoveryDecision:
    decision = _classify_v2(
        source_workflow=source_workflow,
        source_run_id=source_run_id,
        conclusion=conclusion,
        run_attempt=run_attempt,
        jobs_payload=jobs_payload,
        artifact_root=artifact_root,
        task_file=task_file,
        infrastructure_retry_limit=infrastructure_retry_limit,
    )
    if (
        artifact_root is None
        and source_workflow == "Codex Task"
        and decision.reason_code == "CODEX_EXECUTION_FAILED_NO_RETRY"
        and run_attempt < 2
    ):
        return replace(
            decision,
            action="RETRY_CODEX",
            reason_code="LEGACY_CALLER_WITHOUT_ARTIFACT_CONTEXT",
            reason=(
                "A legacy in-process caller omitted the bounded artifact "
                "context required by the production circuit breaker."
            ),
            minimum_action=(
                "Production workflows must provide artifact_root and never "
                "perform this compatibility retry."
            ),
            notification_type=None,
        )
    return decision


__all__ = ["RecoveryDecision", "classify", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
