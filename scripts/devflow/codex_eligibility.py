from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_policy import (
    CodexApproval,
    CodexPolicy,
    CodexPolicyError,
    file_sha256,
    ledger_entries,
    load_object,
)
from context_budget import inspect_context
from execution_router import DEVFLOW_OR_SECURITY_PATTERNS, route_failure
from task_descriptor import TaskDescriptorError, load_task_descriptor


@dataclass(frozen=True)
class EligibilityDecision:
    status: str
    route: str
    codex_allowed: bool
    task_id: str | None
    failure_fingerprint: str | None
    errors: tuple[str, ...]


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _failure_context(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    value = raw.get("failure_context")
    if not isinstance(value, dict):
        return None, ["FAILURE_CONTEXT_MISSING"]
    required_strings = (
        "source_commit_sha",
        "failure_fingerprint",
        "diagnostic_artifact_digest",
        "pre_model_gate_profile",
    )
    for field in required_strings:
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            errors.append(f"FAILURE_CONTEXT_INVALID:{field}")
    source_run_id = value.get("source_run_id")
    if isinstance(source_run_id, bool) or not isinstance(source_run_id, int) or source_run_id <= 0:
        errors.append("FAILURE_CONTEXT_INVALID:source_run_id")
    source_sha = value.get("source_commit_sha")
    if isinstance(source_sha, str) and (
        len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha)
    ):
        errors.append("FAILURE_CONTEXT_INVALID:source_commit_sha")
    digest = value.get("diagnostic_artifact_digest")
    if isinstance(digest, str) and not digest.startswith("sha256:"):
        errors.append("FAILURE_CONTEXT_INVALID:diagnostic_artifact_digest")
    files = value.get("failure_files")
    if not isinstance(files, list) or not files or not all(
        isinstance(item, str) and item.strip() for item in files
    ):
        errors.append("FAILURE_CONTEXT_INVALID:failure_files")
    return value, errors


def evaluate(
    *,
    repo: Path,
    task_file: Path,
    policy_file: Path,
    approval_file: Path,
    ledger_file: Path,
    reproduction_file: Path,
    actor: str,
    now: datetime | None = None,
) -> EligibilityDecision:
    errors: list[str] = []
    task_id: str | None = None
    fingerprint: str | None = None

    try:
        policy = CodexPolicy.from_mapping(load_object(policy_file))
    except CodexPolicyError as exc:
        return EligibilityDecision(
            status="FAIL",
            route="CHATGPT_WEB",
            codex_allowed=False,
            task_id=None,
            failure_fingerprint=None,
            errors=(f"POLICY_INVALID:{exc}",),
        )

    if policy.mode != "enabled":
        errors.append("CODEX_POLICY_DISABLED")
    if actor not in policy.allowed_actors:
        errors.append("ACTOR_NOT_ALLOWED")
    if actor == "github-actions[bot]" or policy.allow_github_actions_bot:
        errors.append("BOT_DISPATCH_FORBIDDEN")
    if policy.auto_recovery_dispatch or policy.retry_failed_codex_job:
        errors.append("AUTOMATIC_CODEX_PATH_FORBIDDEN")

    try:
        raw, task = load_task_descriptor(task_file)
        task_id = task.task_id
    except TaskDescriptorError as exc:
        return EligibilityDecision(
            status="FAIL",
            route="CHATGPT_WEB",
            codex_allowed=False,
            task_id=None,
            failure_fingerprint=None,
            errors=tuple(errors + [f"TASK_DESCRIPTOR_INVALID:{exc}"]),
        )

    context, context_errors = _failure_context(raw)
    errors.extend(context_errors)
    failure_files: list[str] = []
    if context is not None:
        raw_fingerprint = context.get("failure_fingerprint")
        fingerprint = raw_fingerprint.strip() if isinstance(raw_fingerprint, str) else None
        raw_files = context.get("failure_files")
        if isinstance(raw_files, list):
            failure_files = [item.strip() for item in raw_files if isinstance(item, str) and item.strip()]

    route = route_failure("LOCAL_PRODUCT_CODE", failure_files)
    if not route.codex_candidate:
        errors.append(f"ROUTE_NOT_CODEX_CANDIDATE:{route.route}")
    if not 2 <= len(task.allowed_files) <= 5:
        errors.append("ALLOWED_FILE_COUNT_OUTSIDE_2_TO_5")
    if any(_matches(path, DEVFLOW_OR_SECURITY_PATTERNS) for path in task.allowed_files):
        errors.append("FORBIDDEN_SCOPE_CATEGORY")
    if set(failure_files) - set(task.allowed_files):
        errors.append("FAILURE_FILES_NOT_COVERED_BY_ALLOWED_SCOPE")

    try:
        approval = CodexApproval.from_mapping(load_object(approval_file))
    except CodexPolicyError as exc:
        errors.append(f"APPROVAL_INVALID:{exc}")
        approval = None
    if approval is not None:
        current = now or datetime.now(UTC)
        if not approval.is_active(current):
            errors.append("APPROVAL_EXPIRED_OR_NOT_ACTIVE")
        if approval.task_id != task.task_id:
            errors.append("APPROVAL_TASK_MISMATCH")
        if approval.approved_by != actor:
            errors.append("APPROVAL_ACTOR_MISMATCH")
        if approval.descriptor_sha256 != file_sha256(task_file):
            errors.append("APPROVAL_DESCRIPTOR_DIGEST_MISMATCH")
        if approval.failure_fingerprint != fingerprint:
            errors.append("APPROVAL_FINGERPRINT_MISMATCH")
        if raw.get("authorization_id") != approval.approval_id:
            errors.append("APPROVAL_ID_MISMATCH")

    try:
        reproduction = load_object(reproduction_file)
    except CodexPolicyError as exc:
        errors.append(f"REPRODUCTION_RESULT_INVALID:{exc}")
        reproduction = {}
    if reproduction.get("status") != "FAIL":
        errors.append("FAILURE_NOT_REPRODUCIBLE")
    if reproduction.get("failure_fingerprint") != fingerprint:
        errors.append("REPRODUCTION_FINGERPRINT_MISMATCH")
    reproduced_files = reproduction.get("failure_files")
    if not isinstance(reproduced_files, list) or set(reproduced_files) != set(failure_files):
        errors.append("REPRODUCTION_FAILURE_FILES_MISMATCH")

    context_result = inspect_context(repo, task_file, task)
    if context_result.status != "PASS":
        errors.extend(f"CONTEXT_BUDGET:{item}" for item in context_result.violations)

    try:
        entries = ledger_entries(ledger_file)
    except CodexPolicyError as exc:
        errors.append(f"USAGE_LEDGER_INVALID:{exc}")
        entries = []
    task_calls = [item for item in entries if item.get("task_id") == task.task_id]
    fingerprint_calls = [
        item for item in entries if item.get("failure_fingerprint") == fingerprint
    ]
    if len(task_calls) >= policy.calls_per_task:
        errors.append("TASK_CALL_BUDGET_EXHAUSTED")
    if len(fingerprint_calls) >= policy.calls_per_fingerprint:
        errors.append("FINGERPRINT_ALREADY_USED")
    if policy.recovery_generations != 0 or task.max_recovery_generations != 0:
        errors.append("AUTOMATIC_RECOVERY_GENERATION_FORBIDDEN")
    if policy.automatic_second_session != 0 or task.automatic_second_session != 0:
        errors.append("AUTOMATIC_SECOND_SESSION_FORBIDDEN")

    allowed = not errors
    return EligibilityDecision(
        status="PASS" if allowed else "FAIL",
        route="CODEX" if allowed else "CHATGPT_WEB",
        codex_allowed=allowed,
        task_id=task_id,
        failure_fingerprint=fingerprint,
        errors=tuple(errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--policy-file", type=Path, default=Path(".devflow/codex-policy.yaml"))
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument(
        "--ledger-file",
        type=Path,
        default=Path("docs/implementation/CODEX_USAGE_LEDGER.json"),
    )
    parser.add_argument("--reproduction-file", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    decision = evaluate(
        repo=args.repo.resolve(),
        task_file=args.task_file.resolve(),
        policy_file=args.policy_file.resolve(),
        approval_file=args.approval_file.resolve(),
        ledger_file=args.ledger_file.resolve(),
        reproduction_file=args.reproduction_file.resolve(),
        actor=args.actor,
    )
    text = json.dumps(asdict(decision), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if decision.codex_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
