from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

PINNED_ACTION_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
PROTECTED_WORKFLOW_NAMES = {
    "_reusable-codex-thin-worker.yml",
    "codex-task.yml",
    "devflow-state-consistency.yml",
    "devflow-secret-audit.yml",
    "devflow-incident.yml",
    "devflow-relay-health.yml",
    "devflow-post-merge.yml",
}
FORBIDDEN_TEXT = ("pull_request_target", "issue_comment:", "set -x", "curl -v", "printenv", "\nenv\n")


def workflow_on(data: dict[str, Any]) -> Any:
    return data.get("on", data.get(True))


def validate_workflow(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"{path}: YAML parse failed: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: workflow must be an object"]

    if path.name in PROTECTED_WORKFLOW_NAMES:
        lowered = text.lower()
        for pattern in FORBIDDEN_TEXT:
            if pattern in lowered:
                errors.append(f"{path}: forbidden workflow text: {pattern}")

    on_value = workflow_on(data)
    if path.name == "codex-task.yml" and isinstance(on_value, dict):
        allowed_events = {"push", "workflow_dispatch"}
        unexpected = set(on_value) - allowed_events
        if unexpected:
            errors.append(f"{path}: untrusted trigger(s): {sorted(unexpected)}")

    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        errors.append(f"{path}: jobs must be an object")
        return errors

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        environment = job.get("environment")
        permissions = job.get("permissions") or {}
        job_text = yaml.safe_dump(job, sort_keys=False)
        has_agent_secret = "secrets.AGENT_" in job_text
        if environment == "agent-runtime":
            if isinstance(permissions, dict):
                if permissions.get("contents", "read") not in {"read", None}:
                    errors.append(f"{path}:{job_name}: secret job must be contents: read")
                for key in ("issues", "pull-requests", "actions"):
                    if permissions.get(key) == "write":
                        errors.append(f"{path}:{job_name}: secret job cannot write {key}")
        if isinstance(permissions, dict) and permissions.get("contents") == "write":
            if has_agent_secret or environment == "agent-runtime":
                errors.append(f"{path}:{job_name}: write job cannot access agent secrets")

        for step in job.get("steps") or []:
            if not isinstance(step, dict) or "uses" not in step:
                continue
            uses = str(step["uses"])
            if uses.startswith("./"):
                continue
            if not PINNED_ACTION_RE.fullmatch(uses):
                errors.append(f"{path}:{job_name}: action is not pinned to full SHA: {uses}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".github/workflows") / name for name in sorted(PROTECTED_WORKFLOW_NAMES)],
    )
    args = parser.parse_args()
    errors: list[str] = []
    for path in args.paths:
        if not path.is_file():
            errors.append(f"missing workflow: {path}")
            continue
        errors.extend(validate_workflow(path))
    print(f"WORKFLOW_POLICY={'PASS' if not errors else 'FAIL'}")
    print(f"WORKFLOW_POLICY_ERROR_COUNT={len(errors)}")
    for error in errors:
        print(f"WORKFLOW_POLICY_ERROR={error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
