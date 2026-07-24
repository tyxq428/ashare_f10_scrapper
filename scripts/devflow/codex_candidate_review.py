from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from context_budget import inspect_context
from execution_router import route_failure
from task_descriptor import TaskDescriptorError, load_task_descriptor


@dataclass(frozen=True)
class CandidateReview:
    status: str
    route: str
    codex_candidate: bool
    model_invocation: bool
    task_id: str | None
    control_commit_sha: str
    task_commit_sha: str
    errors: tuple[str, ...]
    next_action: str


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"document root must be an object: {path}")
    return value


def review(
    *,
    control_root: Path,
    workspace_root: Path,
    task_file: Path,
    control_commit_sha: str,
    task_commit_sha: str,
) -> CandidateReview:
    errors: list[str] = []
    policy = _load_object(control_root / ".devflow/codex-policy.yaml")
    entrypoints = _load_object(control_root / ".devflow/codex-entrypoints.yaml")
    if policy.get("mode") != "disabled":
        errors.append("CANDIDATE_REVIEW_REQUIRES_DISABLED_POLICY")
    if entrypoints.get("policy_mode") != "disabled":
        errors.append("ENTRYPOINT_MANIFEST_NOT_DISABLED")
    if entrypoints.get("activation", {}).get("mode") != "one_time_reviewed_pr":
        errors.append("ONE_TIME_ACTIVATION_POLICY_MISSING")

    try:
        raw, task = load_task_descriptor(task_file)
    except TaskDescriptorError as exc:
        return CandidateReview(
            status="FAIL",
            route="CHATGPT_WEB",
            codex_candidate=False,
            model_invocation=False,
            task_id=None,
            control_commit_sha=control_commit_sha,
            task_commit_sha=task_commit_sha,
            errors=(f"TASK_DESCRIPTOR_INVALID:{exc}",),
            next_action="repair_descriptor_in_chatgpt_web",
        )

    context = raw.get("failure_context")
    reason_code = context.get("reason_code") if isinstance(context, dict) else ""
    failure_files = context.get("failure_files") if isinstance(context, dict) else []
    assessment = raw.get("web_resolution_assessment")
    decision = route_failure(
        reason_code if isinstance(reason_code, str) else "",
        failure_files if isinstance(failure_files, list) else [],
        web_resolution_assessment=(
            assessment if isinstance(assessment, dict) else None
        ),
    )
    if not decision.codex_candidate:
        errors.append(f"ROUTE_NOT_CODEX_CANDIDATE:{decision.route}")

    context_result = inspect_context(workspace_root, task_file, task)
    if context_result.status != "PASS":
        errors.extend(
            f"CONTEXT_BUDGET:{item}" for item in context_result.violations
        )

    allowed = not errors
    return CandidateReview(
        status="PASS" if allowed else "FAIL",
        route="CODEX_CANDIDATE_REVIEW" if allowed else "CHATGPT_WEB",
        codex_candidate=allowed,
        model_invocation=False,
        task_id=task.task_id,
        control_commit_sha=control_commit_sha,
        task_commit_sha=task_commit_sha,
        errors=tuple(errors),
        next_action=(
            "create_independent_reviewed_activation_pr_and_request_user_approval_again"
            if allowed
            else "continue_in_chatgpt_web"
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--control-commit-sha", required=True)
    parser.add_argument("--task-commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review(
        control_root=args.control_root.resolve(),
        workspace_root=args.workspace_root.resolve(),
        task_file=args.task_file.resolve(),
        control_commit_sha=args.control_commit_sha,
        task_commit_sha=args.task_commit_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.codex_candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
