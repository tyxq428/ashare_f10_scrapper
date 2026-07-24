from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
    for path in sorted(root.rglob(name)):
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
        recovery_generation=0,
        max_recovery_generations=0,
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
    del task_file
    failure_steps = _failure_steps(jobs_payload)
    common = {
        "source_workflow": source_workflow,
        "source_run_id": source_run_id,
        "run_attempt": run_attempt,
        "failure_steps": failure_steps,
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
            minimum_action="Inspect the safe audit summary before any further execution.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if scope_result is not None and scope_result.get("status") == "FAIL":
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SCOPE_GUARD_FAILED",
            reason="A path outside the approved scope was changed.",
            minimum_action="Review the bounded changed-path summary in ChatGPT Web.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if runtime_preflight is not None and runtime_preflight.get("status") == "FAIL":
        codes = runtime_preflight.get("failure_codes", [])
        code_set = {item for item in codes if isinstance(item, str)} if isinstance(codes, list) else set()
        reason_code = (
            "AGENT_RUNTIME_SECRETS_MISSING"
            if code_set & {"MISSING_ENDPOINT", "MISSING_API_KEY", "MISSING_MODEL"}
            else "AGENT_RUNTIME_CONFIGURATION_INVALID"
        )
        return _decision(
            action="HUMAN_REQUIRED",
            reason_code=reason_code,
            reason="The private runtime configuration failed safe validation.",
            minimum_action="Correct the agent-runtime Environment without posting values in chat or GitHub.",
            notification_type="HUMAN_REQUIRED",
            **common,
        )

    if codex_result is not None and codex_result.get("status") in {
        "BLOCKED",
        "NO_CHANGES",
        "UNVERIFIED",
        "FAILURE",
        "TIMEOUT",
    }:
        blocked = codex_result.get("status") == "BLOCKED"
        return _decision(
            action="INTERRUPTED",
            reason_code=("CODEX_BLOCKED_NO_RETRY" if blocked else "CODEX_TERMINAL_NO_RETRY"),
            reason="The single approved Codex session produced a terminal non-publishable result.",
            minimum_action="Inspect the immutable evidence in ChatGPT Web; never rerun this task fingerprint.",
            notification_type="INTERRUPTED",
            **common,
        )

    if _contains_marker(failure_steps, SECURITY_STEP_MARKERS):
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SECURITY_CONTROL_FAILED",
            reason="A security, secret or changed-path scope control failed.",
            minimum_action="Review the bounded safe summary before any further execution.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    if source_workflow in {
        "Devflow State Consistency",
        "Devflow Product Gate",
        "Devflow Post Merge",
    }:
        if source_workflow == "Devflow Product Gate" and _contains_marker(
            failure_steps, MERGE_BOUNDARY_STEP_MARKERS
        ):
            return _decision(
                action="HUMAN_REQUIRED",
                reason_code="AUTO_MERGE_BLOCKED",
                reason="The merge boundary is blocked by a conflict, branch protection or permission policy.",
                minimum_action="Review only the merge boundary; no Codex repair is permitted.",
                notification_type="HUMAN_REQUIRED",
                **common,
            )
        reason_code = {
            "Devflow State Consistency": "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED",
            "Devflow Product Gate": "PRODUCT_GATE_WEB_REPAIR_REQUIRED",
            "Devflow Post Merge": "POST_MERGE_WEB_REPAIR_REQUIRED",
        }[source_workflow]
        return _decision(
            action="INTERRUPTED",
            reason_code=reason_code,
            reason="Framework, state, gate and post-merge failures are handled by ChatGPT Web, not Codex.",
            minimum_action="Diagnose the actual failing branch and paths in ChatGPT Web, then rerun deterministic gates.",
            notification_type="INTERRUPTED",
            **common,
        )

    if source_workflow == "Codex Task" or _contains_marker(failure_steps, CODEX_STEP_MARKERS):
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_SESSION_NO_AUTOMATIC_RETRY",
            reason=(
                "A model-bearing Codex job is single-use. Checkout, setup, "
                "timeout, cancellation and artifact failures after dispatch "
                "cannot rerun the model session."
            ),
            minimum_action=(
                "Return to ChatGPT Web and create a new user-approved Grant "
                "only if a fresh task remains justified."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

    if conclusion in TERMINAL_INFRA_CONCLUSIONS or _contains_marker(failure_steps, INFRA_STEP_MARKERS):
        if run_attempt < infrastructure_retry_limit:
            return _decision(
                action="RETRY",
                reason_code="RETRYABLE_INFRASTRUCTURE",
                reason="A verified runner, setup, dependency or artifact operation may be transient.",
                minimum_action="No user action; rerun only failed infrastructure jobs.",
                notification_type=None,
                **common,
            )
        return _decision(
            action="INTERRUPTED",
            reason_code="INFRASTRUCTURE_RETRY_EXHAUSTED",
            reason="The same infrastructure class failed after the bounded retry budget.",
            minimum_action="Review GitHub service, dependency and repository permission state.",
            notification_type="INTERRUPTED",
            **common,
        )

    if source_workflow == "Devflow Relay Health":
        return _decision(
            action="HUMAN_REQUIRED",
            reason_code="RELAY_HEALTH_UNAVAILABLE",
            reason="Relay authentication, balance, model or protocol health is unavailable.",
            minimum_action="Check the relay account and agent-runtime Environment; no automatic model retry is allowed.",
            notification_type="HUMAN_REQUIRED",
            **common,
        )

    if _contains_marker(failure_steps, SECURITY_STEP_MARKERS):
        return _decision(
            action="SECURITY_BLOCKED",
            reason_code="SECURITY_CONTROL_FAILED",
            reason="A security or scope enforcement step failed.",
            minimum_action="Review the safe summary before any publication.",
            notification_type="SECURITY_BLOCKED",
            **common,
        )

    return _decision(
        action="INTERRUPTED",
        reason_code="UNCLASSIFIED_FAILURE",
        reason="The failure could not be safely classified for automatic recovery.",
        minimum_action="Review bounded job and artifact summaries in ChatGPT Web; do not blindly retry.",
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
