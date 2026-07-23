from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from task_descriptor import TaskDescriptorError, load_task_descriptor

TERMINAL_INFRA_CONCLUSIONS = {"cancelled", "timed_out", "stale", "startup_failure"}
INFRA_STEP_MARKERS = (
    "set up job",
    "checkout",
    "setup-python",
    "setup-node",
    "install deterministic development dependencies",
    "install development dependencies",
    "download audited handoff",
    "upload audited handoff",
    "upload bounded diagnostics",
    "upload diagnostics",
)
SECURITY_STEP_MARKERS = (
    "secret audit",
    "changed-path scope",
    "scope guard",
    "verify manifest",
)
CODEX_STEP_MARKERS = (
    "run one codex thin worker session",
    "run trusted targeted gate",
    "enforce runtime, codex, scope, gate and secret outcomes",
)
MERGE_BOUNDARY_STEP_MARKERS = (
    "reconcile latest main, re-run gate if needed, and merge low-risk candidate",
    "fail closed when automatic merge boundary is blocked",
)


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason_code: str
    reason: str
    minimum_action: str
    notification_type: str | None
    fingerprint: str
    source_workflow: str
    source_run_id: int
    run_attempt: int
    failure_steps: tuple[str, ...]
    recovery_generation: int
    max_recovery_generations: int


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_summary(root: Path | None, name: str) -> dict[str, Any] | None:
    if root is None or not root.exists():
        return None
    matches = sorted(root.rglob(name))
    for path in matches:
        try:
            value = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _failure_steps(jobs_payload: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    jobs = jobs_payload.get("jobs", [])
    if not isinstance(jobs, list):
        return ()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("conclusion") in {"failure", "cancelled", "timed_out"}:
                name = step.get("name")
                if isinstance(name, str) and name not in names:
                    names.append(name)
    return tuple(names)


def _contains_marker(steps: tuple[str, ...], markers: tuple[str, ...]) -> bool:
    lowered = tuple(step.lower() for step in steps)
    return any(marker in step for step in lowered for marker in markers)


def _fingerprint(source: str, reason_code: str, steps: tuple[str, ...]) -> str:
    normalized = "|".join((source, reason_code, *sorted(step.lower() for step in steps)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def _decision(
    *,
    action: str,
    reason_code: str,
    reason: str,
    minimum_action: str,
    notification_type: str | None,
    source_workflow: str,
    source_run_id: int,
    run_attempt: int,
    failure_steps: tuple[str, ...],
    recovery_generation: int,
    max_recovery_generations: int,
) -> RecoveryDecision:
    return RecoveryDecision(
        action=action,
        reason_code=reason_code,
        reason=reason,
        minimum_action=minimum_action,
        notification_type=notification_type,
        fingerprint=_fingerprint(source_workflow, reason_code, failure_steps),
        source_workflow=source_workflow,
        source_run_id=source_run_id,
        run_attempt=run_attempt,
        failure_steps=failure_steps,
        recovery_generation=recovery_generation,
        max_recovery_generations=max_recovery_generations,
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
    failure_steps = _failure_steps(jobs_payload)
    recovery_generation = 0
    max_recovery_generations = 1
    if task_file is not None and task_file.is_file():
        try:
            _raw, task = load_task_descriptor(task_file)
        except TaskDescriptorError:
            task = None
        if task is not None:
            recovery_generation = task.recovery_generation
            max_recovery_generations = task.max_recovery_generations

    common = {
        "source_workflow": source_workflow,
        "source_run_id": source_run_id,
        "run_attempt": run_attempt,
        "failure_steps": failure_steps,
        "recovery_generation": recovery_generation,
        "max_recovery_generations": max_recovery_generations,
    }

    if conclusion == "success":
        if source_workflow == "Devflow Post Merge":
            return _decision(
                action="COMPLETED",
                reason_code="POST_MERGE_PASS",
                reason="Exact-main post-merge verification passed.",
                minimum_action="No action is required.",
                notification_type="COMPLETED",
                **common,
            )
        return _decision(
            action="NOOP",
            reason_code="SOURCE_PASS",
            reason="The source workflow completed successfully.",
            minimum_action="No action is required.",
            notification_type=None,
            **common,
        )

    secret_audit = _find_summary(artifact_root, "secret-audit.json")
    scope_result = _find_summary(artifact_root, "scope-result.json")
    runtime_preflight = _find_summary(artifact_root, "runtime-preflight.json")
    codex_result = _find_summary(artifact_root, "codex-result.json")

    if source_workflow == "Devflow Secret Audit" or (
        secret_audit is not None and secret_audit.get("status") == "FAIL"
    ):
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SECRET_AUDIT_FAILED",
            reason="Secret or private endpoint leakage audit did not pass.",
            minimum_action="Inspect the safe audit summary and rotate credentials only if exposure is confirmed.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if scope_result is not None and scope_result.get("status") == "FAIL":
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SCOPE_GUARD_FAILED",
            reason="The agent changed a path outside the approved task scope.",
            minimum_action="Review the bounded changed-path summary before allowing any publication.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if runtime_preflight is not None and runtime_preflight.get("status") == "FAIL":
        codes = runtime_preflight.get("failure_codes", [])
        code_set = {item for item in codes if isinstance(item, str)} if isinstance(codes, list) else set()
        if code_set & {"MISSING_ENDPOINT", "MISSING_API_KEY", "MISSING_MODEL"}:
            return _decision(
                action="HUMAN_REQUIRED",
                reason_code="AGENT_RUNTIME_SECRETS_MISSING",
                reason="The agent-runtime job cannot see one or more required Environment Secrets.",
                minimum_action=(
                    "Verify the agent-runtime Environment contains AGENT_RESPONSES_ENDPOINT, "
                    "AGENT_API_KEY and AGENT_MODEL, then start one new task generation."
                ),
                notification_type="HUMAN_REQUIRED",
                **common,
            )
        return _decision(
            action="HUMAN_REQUIRED",
            reason_code="AGENT_RUNTIME_CONFIGURATION_INVALID",
            reason="The private agent runtime configuration failed safe shape validation.",
            minimum_action="Correct the agent-runtime Environment configuration without posting values in chat or GitHub.",
            notification_type="HUMAN_REQUIRED",
            **common,
        )

    if codex_result is not None and codex_result.get("status") == "BLOCKED":
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_BLOCKED_NO_RETRY",
            reason="The bounded Codex worker explicitly reported BLOCKED and made no publishable repair.",
            minimum_action=(
                "Use ChatGPT Web Supervisor to inspect the immutable failure context and either repair "
                "directly or create a new correctly scoped task. Do not rerun this Codex generation."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

    if source_workflow == "Devflow State Consistency":
        return _decision(
            action="INTERRUPTED",
            reason_code="STATE_CONSISTENCY_WEB_REPAIR_REQUIRED",
            reason=(
                "State Consistency failures are execution-framework changes and are not eligible for "
                "automatically synthesized Codex repair scopes."
            ),
            minimum_action=(
                "Diagnose and repair the actual failing branch in ChatGPT Web, then rerun deterministic gates."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

    if conclusion in TERMINAL_INFRA_CONCLUSIONS or _contains_marker(failure_steps, INFRA_STEP_MARKERS):
        if run_attempt < infrastructure_retry_limit:
            return _decision(
                action="RETRY",
                reason_code="RETRYABLE_INFRASTRUCTURE",
                reason="A retryable runner, setup, dependency or artifact operation failed.",
                minimum_action="No user action; rerun only failed jobs.",
                notification_type=None,
                **common,
            )
        return _decision(
            action="INTERRUPTED",
            reason_code="INFRASTRUCTURE_RETRY_EXHAUSTED",
            reason="The same infrastructure class failed after the bounded retry budget.",
            minimum_action="Review the bounded job metadata and GitHub service or repository permission state.",
            notification_type="INTERRUPTED",
            **common,
        )

    if source_workflow == "Devflow Relay Health":
        if run_attempt < infrastructure_retry_limit:
            return _decision(
                action="RETRY",
                reason_code="RELAY_HEALTH_TRANSIENT",
                reason="Relay transport or protocol health failed and may be transient.",
                minimum_action="No user action; rerun only the failed job.",
                notification_type=None,
                **common,
            )
        return _decision(
            action="HUMAN_REQUIRED",
            reason_code="RELAY_HEALTH_RETRY_EXHAUSTED",
            reason="Relay authentication, balance, model or protocol health remains unavailable.",
            minimum_action="Check the relay account and agent-runtime Environment, then explicitly resume.",
            notification_type="HUMAN_REQUIRED",
            **common,
        )

    if source_workflow == "Codex Task" or _contains_marker(failure_steps, CODEX_STEP_MARKERS):
        if run_attempt < 2:
            return _decision(
                action="RETRY_CODEX",
                reason_code="CODEX_SESSION_OR_TARGET_GATE_FAILED",
                reason="The bounded Codex session or its targeted gate failed before publication.",
                minimum_action="No user action; rerun the failed Codex job once using the same immutable task descriptor.",
                notification_type=None,
                **common,
            )
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_RETRY_EXHAUSTED",
            reason="The same bounded Codex task failed after one automatic session retry.",
            minimum_action="Review the structured Codex result and targeted gate summary before replanning.",
            notification_type="INTERRUPTED",
            **common,
        )

    if _contains_marker(failure_steps, SECURITY_STEP_MARKERS):
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SECURITY_CONTROL_FAILED",
            reason="A security or scope enforcement step failed.",
            minimum_action="Review the safe summary before any retry or publication.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if source_workflow == "Devflow Product Gate" and _contains_marker(
        failure_steps, MERGE_BOUNDARY_STEP_MARKERS
    ):
        return _decision(
            action="HUMAN_REQUIRED",
            reason_code="AUTO_MERGE_BLOCKED",
            reason=(
                "The low-risk candidate passed its approved gates but the repository merge boundary "
                "is blocked by a conflict, branch protection or permission policy."
            ),
            minimum_action="Review only the merge boundary; no additional Codex repair is requested.",
            notification_type="HUMAN_REQUIRED",
            **common,
        )

    if source_workflow in {"Devflow Product Gate", "Devflow Post Merge"}:
        if recovery_generation < max_recovery_generations:
            return _decision(
                action="CODEX_REPAIR",
                reason_code="BOUNDED_CODE_REPAIR_ELIGIBLE",
                reason="A deterministic code or policy gate failed within an approved bounded recovery scope.",
                minimum_action="No user action; create one constrained Codex recovery generation.",
                notification_type=None,
                **common,
            )
        return _decision(
            action="INTERRUPTED",
            reason_code="CODE_REPAIR_BUDGET_EXHAUSTED",
            reason="The bounded code-repair generation was already used and the gate still fails.",
            minimum_action="Review the failure bundle and decide whether to widen scope or change the implementation plan.",
            notification_type="INTERRUPTED",
            **common,
        )

    return _decision(
        action="INTERRUPTED",
        reason_code="UNCLASSIFIED_FAILURE",
        reason="The failure could not be safely classified for automatic recovery.",
        minimum_action="Review the bounded job and artifact summaries; do not blindly retry.",
        notification_type="INTERRUPTED",
        **common,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--run-attempt", type=int, default=1)
    parser.add_argument("--jobs-json", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--task-file", type=Path)
    parser.add_argument("--infrastructure-retry-limit", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    decision = classify(
        source_workflow=args.source_workflow,
        source_run_id=args.source_run_id,
        conclusion=args.conclusion,
        run_attempt=args.run_attempt,
        jobs_payload=_load_json(args.jobs_json),
        artifact_root=args.artifact_root,
        task_file=args.task_file,
        infrastructure_retry_limit=args.infrastructure_retry_limit,
    )
    payload = asdict(decision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RECOVERY_ACTION={decision.action}")
    print(f"RECOVERY_REASON_CODE={decision.reason_code}")
    print(f"RECOVERY_FINGERPRINT={decision.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
