from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_policy import (
    CodexGrant,
    CodexPolicy,
    CodexPolicyError,
    allowed_files_hash,
    file_sha256,
    ledger_entries,
    load_object,
)
from context_budget import inspect_context
from execution_router import DEVFLOW_OR_SECURITY_PATTERNS, route_failure
from task_descriptor import TaskDescriptorError, load_task_descriptor
from trusted_reproduction import (
    TrustedReproductionError,
    load_trusted_reproduction,
)


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


def _failure_context(
    raw: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    value = raw.get("failure_context")
    if not isinstance(value, dict):
        return None, ["FAILURE_CONTEXT_MISSING"]
    for field in (
        "source_commit_sha",
        "failure_fingerprint",
        "diagnostic_artifact_digest",
        "pre_model_gate_profile",
        "reason_code",
    ):
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            errors.append(f"FAILURE_CONTEXT_INVALID:{field}")
    source_run_id = value.get("source_run_id")
    if (
        isinstance(source_run_id, bool)
        or not isinstance(source_run_id, int)
        or source_run_id <= 0
    ):
        errors.append("FAILURE_CONTEXT_INVALID:source_run_id")
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
    grant_file: Path,
    ledger_file: Path,
    trusted_evidence_file: Path,
    actor: str,
    control_commit_sha: str,
    task_commit_sha: str,
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
    reason_code = ""
    if context is not None:
        raw_fingerprint = context.get("failure_fingerprint")
        fingerprint = (
            raw_fingerprint.strip()
            if isinstance(raw_fingerprint, str)
            else None
        )
        raw_files = context.get("failure_files")
        if isinstance(raw_files, list):
            failure_files = [
                item.strip()
                for item in raw_files
                if isinstance(item, str) and item.strip()
            ]
        raw_reason = context.get("reason_code")
        reason_code = raw_reason.strip() if isinstance(raw_reason, str) else ""

    assessment = raw.get("web_resolution_assessment")
    route = route_failure(
        reason_code,
        failure_files,
        web_resolution_assessment=(
            assessment if isinstance(assessment, dict) else None
        ),
    )
    if not route.codex_candidate:
        errors.append(f"ROUTE_NOT_CODEX_CANDIDATE:{route.route}")
    if not 2 <= len(task.allowed_files) <= 5:
        errors.append("ALLOWED_FILE_COUNT_OUTSIDE_2_TO_5")
    if any(
        _matches(path, DEVFLOW_OR_SECURITY_PATTERNS)
        for path in task.allowed_files
    ):
        errors.append("FORBIDDEN_SCOPE_CATEGORY")
    if set(failure_files) - set(task.allowed_files):
        errors.append("FAILURE_FILES_NOT_COVERED_BY_ALLOWED_SCOPE")

    try:
        evidence = load_trusted_reproduction(trusted_evidence_file)
    except TrustedReproductionError as exc:
        errors.append(f"TRUSTED_EVIDENCE_INVALID:{exc}")
        evidence = None
    if evidence is not None and context is not None:
        comparisons = {
            "CONTROL_COMMIT_MISMATCH": (
                evidence.control_commit_sha,
                control_commit_sha,
            ),
            "TASK_COMMIT_MISMATCH": (
                evidence.task_commit_sha,
                task_commit_sha,
            ),
            "SOURCE_RUN_MISMATCH": (
                evidence.source_run_id,
                context.get("source_run_id"),
            ),
            "SOURCE_COMMIT_MISMATCH": (
                evidence.source_commit_sha,
                context.get("source_commit_sha"),
            ),
            "ARTIFACT_DIGEST_MISMATCH": (
                evidence.diagnostic_artifact_digest,
                context.get("diagnostic_artifact_digest"),
            ),
            "GATE_PROFILE_MISMATCH": (
                evidence.gate_profile,
                context.get("pre_model_gate_profile"),
            ),
            "FAILURE_FINGERPRINT_MISMATCH": (
                evidence.failure_fingerprint,
                fingerprint,
            ),
        }
        for code, (actual, expected) in comparisons.items():
            if actual != expected:
                errors.append(code)
        if set(evidence.failure_files) != set(failure_files):
            errors.append("REPRODUCTION_FAILURE_FILES_MISMATCH")

    try:
        grant = CodexGrant.from_mapping(load_object(grant_file))
    except CodexPolicyError as exc:
        errors.append(f"GRANT_INVALID:{exc}")
        grant = None
    if grant is not None:
        current = now or datetime.now(UTC)
        if not grant.is_active(current):
            errors.append("GRANT_EXPIRED_USED_OR_NOT_ACTIVE")
        if grant.task_id != task.task_id:
            errors.append("GRANT_TASK_MISMATCH")
        if grant.approved_by != actor:
            errors.append("GRANT_ACTOR_MISMATCH")
        if grant.descriptor_sha256 != file_sha256(task_file):
            errors.append("GRANT_DESCRIPTOR_DIGEST_MISMATCH")
        if grant.task_commit_sha != task_commit_sha:
            errors.append("GRANT_TASK_COMMIT_MISMATCH")
        if grant.failure_fingerprint != fingerprint:
            errors.append("GRANT_FINGERPRINT_MISMATCH")
        if grant.allowed_files_hash != allowed_files_hash(task.allowed_files):
            errors.append("GRANT_ALLOWED_FILES_HASH_MISMATCH")
        if context is not None:
            if grant.source_run_id != context.get("source_run_id"):
                errors.append("GRANT_SOURCE_RUN_MISMATCH")
            if grant.source_commit_sha != context.get("source_commit_sha"):
                errors.append("GRANT_SOURCE_COMMIT_MISMATCH")
        if raw.get("authorization_id") != grant.grant_id:
            errors.append("GRANT_ID_MISMATCH")

    context_result = inspect_context(repo, task_file, task)
    if context_result.status != "PASS":
        errors.extend(
            f"CONTEXT_BUDGET:{item}"
            for item in context_result.violations
        )

    try:
        entries = ledger_entries(ledger_file)
    except CodexPolicyError as exc:
        errors.append(f"USAGE_LEDGER_INVALID:{exc}")
        entries = []
    active_entries = [
        item
        for item in entries
        if item.get("state") in {"RESERVED", "CONSUMED"}
    ]
    if any(item.get("task_id") == task.task_id for item in active_entries):
        errors.append("TASK_CALL_BUDGET_EXHAUSTED")
    if any(
        item.get("failure_fingerprint") == fingerprint
        for item in active_entries
    ):
        errors.append("FINGERPRINT_ALREADY_USED")
    if grant is not None and any(
        item.get("grant_id") == grant.grant_id for item in active_entries
    ):
        errors.append("GRANT_ALREADY_CONSUMED")
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
    parser.add_argument(
        "--policy-file",
        type=Path,
        default=Path(".devflow/codex-policy.yaml"),
    )
    parser.add_argument("--grant-file", type=Path, required=True)
    parser.add_argument(
        "--ledger-file",
        type=Path,
        default=Path("docs/implementation/CODEX_USAGE_LEDGER.json"),
    )
    parser.add_argument("--trusted-evidence-file", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--control-commit-sha", required=True)
    parser.add_argument("--task-commit-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    decision = evaluate(
        repo=args.repo.resolve(),
        task_file=args.task_file.resolve(),
        policy_file=args.policy_file.resolve(),
        grant_file=args.grant_file.resolve(),
        ledger_file=args.ledger_file.resolve(),
        trusted_evidence_file=args.trusted_evidence_file.resolve(),
        actor=args.actor,
        control_commit_sha=args.control_commit_sha,
        task_commit_sha=args.task_commit_sha,
    )
    text = json.dumps(asdict(decision), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if decision.codex_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
