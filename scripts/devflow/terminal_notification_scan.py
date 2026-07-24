from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from notification_event import NotificationValidationError, validate_notification

STATE_PATH_RE = re.compile(r"^docs/implementation/([^/]+)/task_state\.yaml$")
ZERO_SHA = "0" * 40


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _show_json(repo: Path, revision: str, path: str) -> dict[str, Any] | None:
    result = _run_git(repo, "show", f"{revision}:{path}", check=False)
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise NotificationValidationError(
            f"task state is not valid JSON at {revision}:{path}"
        ) from exc
    if not isinstance(value, dict):
        raise NotificationValidationError(
            f"task state root must be an object at {revision}:{path}"
        )
    return value


def _generation(state: dict[str, Any] | None) -> int:
    if state is None:
        return -1
    notification = state.get("notification")
    if not isinstance(notification, dict):
        return -1
    value = notification.get("generation")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return -1


def _reason_code(state: dict[str, Any]) -> str:
    acceptance = state.get("acceptance")
    if isinstance(acceptance, dict):
        value = acceptance.get("reason_code")
        if isinstance(value, str) and value:
            return value
    return "TASK_COMPLETED"


def scan_terminal_completions(
    *,
    repo: Path,
    before: str,
    after: str,
    repository: str,
    source_run_id: int,
) -> list[dict[str, Any]]:
    if before == ZERO_SHA:
        return []
    changed = _run_git(
        repo,
        "diff",
        "--name-only",
        before,
        after,
        "--",
        "docs/implementation",
    ).stdout.splitlines()
    events: list[dict[str, Any]] = []
    for path in sorted(set(changed)):
        if not STATE_PATH_RE.fullmatch(path):
            continue
        current = _show_json(repo, after, path)
        if current is None:
            continue
        previous = _show_json(repo, before, path)
        notification = current.get("notification")
        if not isinstance(notification, dict):
            continue
        current_generation = _generation(current)
        if current_generation <= _generation(previous):
            continue
        if notification.get("last_type") != "COMPLETED":
            continue
        if notification.get("acknowledged") is not False:
            continue
        task_id = current.get("task_id")
        if not isinstance(task_id, str):
            raise NotificationValidationError(f"task_id missing in {path}")
        pull_request = current.get("pull_request")
        target_url = None
        if isinstance(pull_request, int) and not isinstance(pull_request, bool) and pull_request > 0:
            target_url = f"https://github.com/{repository}/pull/{pull_request}"
        payload = {
            "task_id": task_id,
            "action": "COMPLETED",
            "notification_type": "COMPLETED",
            "reason_code": _reason_code(current),
            "reason": (
                "Canonical task state reached DONE / COMPLETED / PASS and "
                "post-merge verification passed."
            ),
            "minimum_action": "No action is required.",
            "fingerprint": f"task-completed:{task_id}:g{current_generation}",
            "source_workflow": "Devflow State Consistency",
            "source_run_id": source_run_id,
            "failure_steps": [],
            "target_url": target_url,
        }
        validated = validate_notification(
            repo=repo,
            repository=repository,
            payload=payload,
        )
        events.append(payload | {"marker": validated["marker"]})
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events = scan_terminal_completions(
        repo=args.repo.resolve(),
        before=args.before,
        after=args.after,
        repository=args.repository,
        source_run_id=args.source_run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(events, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"TERMINAL_NOTIFICATION_EVENTS={len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
