from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ALLOWED_NOTIFICATION_TYPES = {
    "COMPLETED",
    "INTERRUPTED",
    "HUMAN_REQUIRED",
    "SECURITY_BLOCKED",
}
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,119}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REASON_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{1,99}$")
FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")


class NotificationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedTask:
    task_id: str
    state_path: Path
    relative_state_path: str
    index_entry: dict[str, Any]
    state: dict[str, Any]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NotificationValidationError(f"cannot load JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise NotificationValidationError(f"JSON root must be an object: {path}")
    return value


def _safe_text(value: Any, field: str, *, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise NotificationValidationError(f"{field} must be a string")
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text and not allow_empty:
        raise NotificationValidationError(f"{field} must not be empty")
    if len(text) > maximum:
        raise NotificationValidationError(f"{field} exceeds {maximum} characters")
    for character in text:
        if character in {"\n", "\t"}:
            continue
        if unicodedata.category(character) == "Cc":
            raise NotificationValidationError(f"{field} contains a control character")
    return text


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise NotificationValidationError(f"{field} must be a positive integer")
    return value


def _state_acceptance_status(state: dict[str, Any]) -> str | None:
    acceptance = state.get("acceptance")
    if isinstance(acceptance, dict):
        value = acceptance.get("status")
        return value if isinstance(value, str) else None
    value = state.get("research_acceptance_status")
    return value if isinstance(value, str) else None


def _state_security_status(state: dict[str, Any]) -> str | None:
    value = state.get("security_status")
    if isinstance(value, str):
        return value
    return "PASS" if state.get("status") == "DONE" else None


def _strict_done(state: dict[str, Any]) -> bool:
    human_gate = state.get("human_gate")
    post_merge = state.get("post_merge")
    notification = state.get("notification")
    return (
        state.get("status") == "DONE"
        and state.get("execution_status") == "COMPLETED"
        and _state_acceptance_status(state) == "PASS"
        and _state_security_status(state) == "PASS"
        and isinstance(post_merge, dict)
        and post_merge.get("status") == "PASS"
        and isinstance(human_gate, dict)
        and human_gate.get("required") is False
        and isinstance(notification, dict)
        and notification.get("last_type") == "COMPLETED"
        and notification.get("acknowledged") is False
    )


def resolve_task(repo: Path, task_id: str | None = None) -> ResolvedTask:
    root = repo.resolve()
    index_path = root / "docs/implementation/ACTIVE_TASKS.yaml"
    index = _load_object(index_path)
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        raise NotificationValidationError("ACTIVE_TASKS.tasks must be an array")

    entries = [item for item in tasks if isinstance(item, dict)]
    if task_id is None:
        candidates = [item for item in entries if item.get("status") != "DONE"]
        if len(candidates) != 1:
            raise NotificationValidationError(
                "task_id is required unless exactly one non-DONE task is registered"
            )
        entry = candidates[0]
        raw_task_id = entry.get("task_id")
    else:
        raw_task_id = task_id
        matches = [item for item in entries if item.get("task_id") == task_id]
        if len(matches) != 1:
            raise NotificationValidationError(
                f"task_id must appear exactly once in ACTIVE_TASKS: {task_id}"
            )
        entry = matches[0]

    if not isinstance(raw_task_id, str) or not TASK_ID_RE.fullmatch(raw_task_id):
        raise NotificationValidationError("task_id has an invalid format")
    state_path_raw = entry.get("state_path")
    if not isinstance(state_path_raw, str) or not state_path_raw.strip():
        raise NotificationValidationError("ACTIVE_TASKS entry is missing state_path")
    state_path = (root / state_path_raw).resolve()
    try:
        state_path.relative_to(root)
    except ValueError as exc:
        raise NotificationValidationError("state_path escapes the repository") from exc
    if state_path.name != "task_state.yaml":
        raise NotificationValidationError("state_path must end with task_state.yaml")

    state = _load_object(state_path)
    if state.get("task_id") != raw_task_id:
        raise NotificationValidationError("task_state task_id does not match ACTIVE_TASKS")
    if entry.get("status") != state.get("status"):
        raise NotificationValidationError("ACTIVE_TASKS status does not match task_state")

    return ResolvedTask(
        task_id=raw_task_id,
        state_path=state_path,
        relative_state_path=state_path.relative_to(root).as_posix(),
        index_entry=entry,
        state=state,
    )


def _validated_target_url(
    value: Any,
    *,
    repository: str,
    source_run_id: int,
    pull_request: Any,
) -> str:
    default = f"https://github.com/{repository}/actions/runs/{source_run_id}"
    if value in (None, ""):
        if isinstance(pull_request, int) and not isinstance(pull_request, bool) and pull_request > 0:
            return f"https://github.com/{repository}/pull/{pull_request}"
        return default
    url = _safe_text(value, "target_url", maximum=500)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise NotificationValidationError("target_url must use https://github.com")
    if not parsed.path.startswith(f"/{repository}/"):
        raise NotificationValidationError("target_url must stay inside the current repository")
    if parsed.username or parsed.password or parsed.fragment:
        raise NotificationValidationError("target_url contains forbidden components")
    return url


def validate_notification(
    *,
    repo: Path,
    repository: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not REPOSITORY_RE.fullmatch(repository):
        raise NotificationValidationError("repository must use owner/name format")

    task_value = payload.get("task_id")
    if task_value is not None and not isinstance(task_value, str):
        raise NotificationValidationError("task_id must be a string when provided")
    task = resolve_task(repo, task_value)

    notification_type = _safe_text(
        payload.get("notification_type"),
        "notification_type",
        maximum=32,
    )
    if notification_type not in ALLOWED_NOTIFICATION_TYPES:
        raise NotificationValidationError(
            f"notification_type is not valuable: {notification_type}"
        )
    action = _safe_text(payload.get("action"), "action", maximum=32)
    if action != notification_type:
        raise NotificationValidationError("action must equal notification_type")

    reason_code = _safe_text(payload.get("reason_code"), "reason_code", maximum=100)
    if not REASON_CODE_RE.fullmatch(reason_code):
        raise NotificationValidationError("reason_code has an invalid format")
    reason = _safe_text(payload.get("reason"), "reason", maximum=600)
    minimum_action = _safe_text(
        payload.get("minimum_action"),
        "minimum_action",
        maximum=500,
    )
    fingerprint = _safe_text(
        payload.get("fingerprint"),
        "fingerprint",
        maximum=160,
    )
    if not FINGERPRINT_RE.fullmatch(fingerprint):
        raise NotificationValidationError("fingerprint has an invalid format")
    source_workflow = _safe_text(
        payload.get("source_workflow"),
        "source_workflow",
        maximum=120,
    )
    source_run_id = _positive_int(payload.get("source_run_id"), "source_run_id")

    raw_steps = payload.get("failure_steps", [])
    if not isinstance(raw_steps, list) or len(raw_steps) > 20:
        raise NotificationValidationError("failure_steps must be an array of at most 20 items")
    failure_steps = [
        _safe_text(item, "failure_steps item", maximum=160)
        for item in raw_steps
    ]

    notification = task.state.get("notification")
    generation = None
    if isinstance(notification, dict):
        raw_generation = notification.get("generation")
        if (
            isinstance(raw_generation, int)
            and not isinstance(raw_generation, bool)
            and raw_generation >= 0
        ):
            generation = raw_generation

    if notification_type == "COMPLETED":
        if not _strict_done(task.state):
            raise NotificationValidationError(
                "COMPLETED requires canonical DONE / COMPLETED / PASS, "
                "post-merge PASS and an unacknowledged completion generation"
            )
        if task.index_entry.get("status") != "DONE":
            raise NotificationValidationError(
                "COMPLETED requires ACTIVE_TASKS to record DONE"
            )
        if generation is None or generation <= 0:
            raise NotificationValidationError(
                "COMPLETED requires a positive notification generation"
            )
        expected_fingerprint = f"task-completed:{task.task_id}:g{generation}"
        if fingerprint != expected_fingerprint:
            raise NotificationValidationError(
                "COMPLETED fingerprint must bind the canonical generation"
            )
        if source_workflow != "Devflow State Consistency":
            raise NotificationValidationError(
                "COMPLETED must originate from Devflow State Consistency"
            )
        if failure_steps:
            raise NotificationValidationError(
                "COMPLETED must not contain failure steps"
            )
    elif task.state.get("status") == "DONE":
        raise NotificationValidationError(
            "non-completion notifications are forbidden for a DONE task"
        )

    target_url = _validated_target_url(
        payload.get("target_url"),
        repository=repository,
        source_run_id=source_run_id,
        pull_request=task.state.get("pull_request"),
    )
    issue_number = None
    if isinstance(notification, dict):
        value = notification.get("control_issue_number")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            issue_number = value

    return {
        "task_id": task.task_id,
        "task_title": _safe_text(
            task.state.get("title", task.task_id),
            "task title",
            maximum=160,
        ),
        "state_path": task.relative_state_path,
        "state_status": task.state.get("status"),
        "notification_generation": generation,
        "notification_type": notification_type,
        "action": action,
        "reason_code": reason_code,
        "reason": reason,
        "minimum_action": minimum_action,
        "fingerprint": fingerprint,
        "source_workflow": source_workflow,
        "source_run_id": source_run_id,
        "source_url": f"https://github.com/{repository}/actions/runs/{source_run_id}",
        "failure_steps": failure_steps,
        "target_url": target_url,
        "control_issue_number": issue_number,
        "control_title": f"[TASK CONTROL] {task.task_id}",
        "marker": f"devflow-root:{fingerprint}:{notification_type}",
    }


def _truncate(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    return value[: max(0, maximum - 1)].rstrip() + "…"


def render_bark_message(
    validated: dict[str, Any],
    *,
    repository: str,
    group: str | None = None,
) -> dict[str, str]:
    repo_name = repository.split("/", 1)[1]
    kind = validated["notification_type"]
    title_suffix = {
        "COMPLETED": "任务已完成",
        "INTERRUPTED": "任务已中断",
        "HUMAN_REQUIRED": "需要人工操作",
        "SECURITY_BLOCKED": "安全门禁阻断",
    }[kind]
    icon = {
        "COMPLETED": "✅",
        "INTERRUPTED": "⏸",
        "HUMAN_REQUIRED": "👤",
        "SECURITY_BLOCKED": "🛡",
    }[kind]
    title = _truncate(f"{icon} {repo_name} · {title_suffix}", 120)
    body = "\n".join(
        (
            validated["task_id"],
            f"分类：{validated['reason_code']}",
            validated["reason"],
            f"操作：{validated['minimum_action']}",
            f"来源：{validated['source_workflow']} #{validated['source_run_id']}",
        )
    )
    group_value = group or f"{repo_name.replace('_', '-')}-devflow"
    return {
        "title": title,
        "body": _truncate(body, 900),
        "group": _truncate(group_value, 64),
        "level": "active" if kind == "COMPLETED" else "timeSensitive",
        "url": validated["target_url"],
        "isArchive": "1",
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve-task")
    resolve_parser.add_argument("--repo", type=Path, default=Path("."))
    resolve_parser.add_argument("--task-id")
    resolve_parser.add_argument("--output", type=Path)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--repo", type=Path, default=Path("."))
    prepare_parser.add_argument("--repository", required=True)
    prepare_parser.add_argument("--payload", type=Path, required=True)
    prepare_parser.add_argument("--validated-output", type=Path, required=True)
    prepare_parser.add_argument("--bark-output", type=Path, required=True)
    prepare_parser.add_argument("--group")

    args = parser.parse_args()
    if args.command == "resolve-task":
        task = resolve_task(args.repo, args.task_id)
        value = {
            "task_id": task.task_id,
            "state_path": task.relative_state_path,
        }
        if args.output:
            _write_json(args.output, value)
        print(json.dumps(value, sort_keys=True))
        return 0

    payload = _load_object(args.payload)
    validated = validate_notification(
        repo=args.repo,
        repository=args.repository,
        payload=payload,
    )
    bark = render_bark_message(
        validated,
        repository=args.repository,
        group=args.group,
    )
    _write_json(args.validated_output, validated)
    _write_json(args.bark_output, bark)
    print(f"NOTIFICATION_TASK_ID={validated['task_id']}")
    print(f"NOTIFICATION_TYPE={validated['notification_type']}")
    print(f"NOTIFICATION_MARKER={validated['marker']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
