from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TASK_STATUSES = {
    "PLANNING",
    "READY",
    "RUNNING",
    "VERIFYING",
    "WAITING_HUMAN",
    "BLOCKED",
    "POST_MERGE_BLOCKED",
    "DONE",
}
EXECUTION_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "BLOCKED"}
ACCEPTANCE_STATUSES = {"PENDING", "PASS", "REVIEW_REQUIRED", "FAIL"}
POST_MERGE_STATUSES = {"PENDING", "RUNNING", "PASS", "FAIL"}


class StateError(ValueError):
    pass


def load_json_yaml(path: Path) -> dict[str, Any]:
    """Load a JSON document stored with a .yaml extension.

    JSON is a strict YAML subset and avoids parser-version ambiguity in CI.
    """

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot load state file: {path}") from exc
    if not isinstance(value, dict):
        raise StateError(f"state root must be an object: {path}")
    return value


def _require(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        raise StateError(f"{key} must be {expected.__name__}")
    return value


def stage_number(stage: str) -> int:
    if len(stage) != 3 or not stage.startswith("W") or not stage[1:].isdigit():
        raise StateError(f"invalid stage: {stage}")
    return int(stage[1:])


@dataclass(frozen=True)
class TaskState:
    task_id: str
    status: str
    execution_status: str
    research_acceptance_status: str
    working_branch: str
    current_stage: str
    last_completed_stage: str | None
    post_merge_status: str
    human_required: bool

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TaskState":
        schema_version = _require(data, "schema_version", int)
        if schema_version != 1:
            raise StateError(f"unsupported schema_version: {schema_version}")
        _require(data, "state_revision", int)
        task_id = _require(data, "task_id", str)
        status = _require(data, "status", str)
        execution_status = _require(data, "execution_status", str)
        acceptance_status = _require(data, "research_acceptance_status", str)
        working_branch = _require(data, "working_branch", str)
        current_stage = _require(data, "current_stage", str)
        stage_number(current_stage)

        last_completed = data.get("last_completed_stage")
        if last_completed is not None:
            if not isinstance(last_completed, str):
                raise StateError("last_completed_stage must be string or null")
            if stage_number(last_completed) >= stage_number(current_stage):
                raise StateError("last_completed_stage must precede current_stage")

        if status not in TASK_STATUSES:
            raise StateError(f"invalid task status: {status}")
        if execution_status not in EXECUTION_STATUSES:
            raise StateError(f"invalid execution_status: {execution_status}")
        if acceptance_status not in ACCEPTANCE_STATUSES:
            raise StateError(f"invalid research_acceptance_status: {acceptance_status}")

        post_merge = _require(data, "post_merge", dict)
        post_merge_status = _require(post_merge, "status", str)
        if post_merge_status not in POST_MERGE_STATUSES:
            raise StateError(f"invalid post_merge status: {post_merge_status}")

        human_gate = _require(data, "human_gate", dict)
        human_required = _require(human_gate, "required", bool)
        if human_required:
            for key in ("reason", "minimum_action", "resume_from"):
                value = human_gate.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise StateError(f"human_gate.{key} is required")

        if status == "DONE":
            if execution_status != "COMPLETED":
                raise StateError("DONE requires execution_status COMPLETED")
            if post_merge_status != "PASS":
                raise StateError("DONE requires post_merge PASS")
            if human_required:
                raise StateError("DONE cannot require a human gate")

        for key in (
            "title",
            "base_sha_at_start",
            "last_product_commit_sha",
            "last_successful_step",
            "next_action",
            "updated_at_utc",
        ):
            _require(data, key, str)
        _require(data, "gate_results", dict)
        _require(data, "retry_budget", dict)
        _require(data, "notification", dict)

        return cls(
            task_id=task_id,
            status=status,
            execution_status=execution_status,
            research_acceptance_status=acceptance_status,
            working_branch=working_branch,
            current_stage=current_stage,
            last_completed_stage=last_completed,
            post_merge_status=post_merge_status,
            human_required=human_required,
        )


def required_task_files(task_dir: Path, state: TaskState) -> list[Path]:
    required = [
        task_dir / "00_contract.md",
        task_dir / "01_master_plan.md",
        task_dir / "task_state.yaml",
        task_dir / "STATUS.md",
        task_dir / "HANDOFF.md",
        task_dir / "DECISIONS.md",
        task_dir / f"{state.current_stage}_plan.md",
    ]
    if state.last_completed_stage is not None:
        for number in range(stage_number(state.last_completed_stage) + 1):
            stage = f"W{number:02d}"
            required.extend([task_dir / f"{stage}_plan.md", task_dir / f"{stage}_result.md"])
    if state.status == "DONE":
        required.append(task_dir / "FINAL_REPORT.md")
    return required
