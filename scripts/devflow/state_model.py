from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STAGE_RE = re.compile(r"^W(?P<number>\d{2})$")
TERMINAL_STATUSES = {"DONE", "CANCELLED", "SUPERSEDED"}
ACTIVE_STATUSES = {
    "RECEIVED",
    "CONTRACTING",
    "BASELINE_AUDIT",
    "PLANNING",
    "READY",
    "RUNNING",
    "VERIFYING",
    "PRE_MERGE",
    "MERGED",
    "POST_MERGE",
    "BLOCKED",
    "WAITING_HUMAN",
    "SECURITY_BLOCKED",
}
EXECUTION_STATUSES = {"PENDING", "RUNNING", "SUCCESS", "FAILED", "BLOCKED"}
ACCEPTANCE_STATUSES = {
    "PENDING",
    "PASS",
    "PASS_WITH_GAPS",
    "REVIEW_REQUIRED",
    "FAIL",
}


def load_json_yaml(path: Path) -> dict[str, Any]:
    """Load JSON-compatible YAML without adding a runtime dependency."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: expected JSON-compatible YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def write_json_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def stage_number(value: str | None) -> int | None:
    if value is None:
        return None
    match = STAGE_RE.fullmatch(value)
    return int(match.group("number")) if match else None


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def validate_state_shape(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "state_revision",
        "task_id",
        "title",
        "status",
        "execution_status",
        "acceptance_status",
        "current_stage",
        "working_branch",
        "delivery_base",
        "base_sha_at_start",
        "last_product_commit_sha",
        "post_merge_gate",
        "human_gate",
        "next_action",
        "recovery_entry",
        "notification_generation",
        "updated_at_utc",
    }
    for key in sorted(required - state.keys()):
        errors.append(f"missing state key: {key}")

    status = state.get("status")
    if status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        errors.append(f"invalid status: {status!r}")
    if state.get("execution_status") not in EXECUTION_STATUSES:
        errors.append(f"invalid execution_status: {state.get('execution_status')!r}")
    if state.get("acceptance_status") not in ACCEPTANCE_STATUSES:
        errors.append(f"invalid acceptance_status: {state.get('acceptance_status')!r}")

    current_stage = state.get("current_stage")
    if stage_number(current_stage) is None:
        errors.append(f"invalid current_stage: {current_stage!r}")
    last_stage = state.get("last_completed_stage")
    if last_stage is not None and stage_number(last_stage) is None:
        errors.append(f"invalid last_completed_stage: {last_stage!r}")
    if (
        stage_number(current_stage) is not None
        and stage_number(last_stage) is not None
        and stage_number(last_stage) >= stage_number(current_stage)
        and status not in TERMINAL_STATUSES
    ):
        errors.append("last_completed_stage must precede current_stage while task is active")

    human_gate = state.get("human_gate")
    if not isinstance(human_gate, dict):
        errors.append("human_gate must be an object")
    else:
        required_human = {"required", "reason", "minimum_action"}
        for key in sorted(required_human - human_gate.keys()):
            errors.append(f"missing human_gate key: {key}")
        if human_gate.get("required"):
            if not str(human_gate.get("reason") or "").strip():
                errors.append("human_gate.required needs a non-empty reason")
            if not str(human_gate.get("minimum_action") or "").strip():
                errors.append("human_gate.required needs a minimum_action")
            if status not in {"WAITING_HUMAN", "BLOCKED", "SECURITY_BLOCKED"}:
                errors.append("human_gate.required requires a blocked or waiting status")

    if status == "DONE":
        if state.get("execution_status") != "SUCCESS":
            errors.append("DONE requires execution_status SUCCESS")
        if state.get("acceptance_status") == "PENDING":
            errors.append("DONE requires a terminal acceptance_status")
        if state.get("post_merge_gate") != "PASS":
            errors.append("DONE requires post_merge_gate PASS")
        if isinstance(human_gate, dict) and human_gate.get("required"):
            errors.append("DONE cannot require human intervention")

    if not isinstance(state.get("notification_generation"), int):
        errors.append("notification_generation must be an integer")
    if not isinstance(state.get("state_revision"), int):
        errors.append("state_revision must be an integer")
    return errors


def render_status(state: dict[str, Any]) -> str:
    human = state.get("human_gate", {})
    return (
        "# 当前状态\n\n"
        f"- 任务：`{state['task_id']}` — {state['title']}\n"
        f"- 生命周期：`{state['status']}`\n"
        f"- 执行状态：`{state['execution_status']}`\n"
        f"- 验收状态：`{state['acceptance_status']}`\n"
        f"- 已完成阶段：`{state.get('last_completed_stage') or '无'}`\n"
        f"- 当前阶段：`{state['current_stage']}`\n"
        f"- 分支：`{state['working_branch']}`\n"
        f"- PR：`{state.get('pull_request') or '尚未创建'}`\n"
        f"- 下一动作：{state['next_action']}\n"
        f"- 人工介入：{'是' if human.get('required') else '否'}\n"
        f"- Post-merge：`{state['post_merge_gate']}`\n"
        f"- 更新时间：`{state['updated_at_utc']}`\n"
    )


def render_handoff(state: dict[str, Any]) -> str:
    human = state.get("human_gate", {})
    minimum_action = human.get("minimum_action") if human.get("required") else "无"
    reason = human.get("reason") if human.get("required") else "无"
    return (
        "# HANDOFF\n\n"
        "## Canonical state\n\n"
        f"- Task：`{state['task_id']}`\n"
        f"- Status：`{state['status']}` / `{state['execution_status']}` / "
        f"`{state['acceptance_status']}`\n"
        f"- Current stage：`{state['current_stage']}`\n"
        f"- Last completed stage：`{state.get('last_completed_stage') or '无'}`\n"
        f"- Branch：`{state['working_branch']}`\n"
        f"- PR：`{state.get('pull_request') or '尚未创建'}`\n"
        f"- Last verified product commit：`{state['last_product_commit_sha']}`\n\n"
        "## Exact next action\n\n"
        f"{state['next_action']}\n\n"
        "## Human gate\n\n"
        f"- Required：{'yes' if human.get('required') else 'no'}\n"
        f"- Reason：{reason}\n"
        f"- Minimum action：{minimum_action}\n\n"
        "## Recovery entry\n\n"
        "Read this state file, the current branch head and Checks, then the current "
        "stage plan. Chat history is supplementary only.\n"
    )
