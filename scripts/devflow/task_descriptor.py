from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TaskDescriptorError(ValueError):
    pass


BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RISK_CLASSES = {"low", "medium", "high"}


def _positive_int_or_zero(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TaskDescriptorError(f"{field} must be a non-negative integer")
    return value


def _string_list(data: dict[str, Any], field: str, *, non_empty: bool = True) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise TaskDescriptorError(f"{field} must be a string array")
    if non_empty and not value:
        raise TaskDescriptorError(f"{field} must not be empty")
    return tuple(item.strip() for item in value)


@dataclass(frozen=True)
class TaskDescriptor:
    task_id: str
    objective: str
    base_branch: str
    publish_branch: str
    allowed_files: tuple[str, ...]
    forbidden_patterns: tuple[str, ...]
    required_changes: tuple[str, ...]
    gate_profile: str
    full_gate_profile: str
    post_merge_profile: str
    reasoning_effort: str
    session_limit: int
    automatic_second_session: int
    recovery_generation: int
    max_recovery_generations: int
    risk_class: str
    auto_merge: bool
    notify_completion: bool
    expected_base_sha: str
    parent_task_id: str | None
    parent_run_id: int | None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TaskDescriptor":
        if data.get("schema_version") != 1:
            raise TaskDescriptorError("schema_version must be 1")

        required_strings = (
            "task_id",
            "objective",
            "base_branch",
            "publish_branch",
            "gate_profile",
            "full_gate_profile",
            "post_merge_profile",
            "reasoning_effort",
            "risk_class",
            "expected_base_sha",
        )
        values: dict[str, str] = {}
        for field in required_strings:
            value = data.get(field)
            if not isinstance(value, str) or not value.strip():
                raise TaskDescriptorError(f"{field} must be a non-empty string")
            values[field] = value.strip()

        if values["reasoning_effort"] != "low":
            raise TaskDescriptorError("reasoning_effort must be low")
        if values["risk_class"] not in RISK_CLASSES:
            raise TaskDescriptorError("risk_class must be low, medium or high")
        if not BRANCH_RE.fullmatch(values["base_branch"]):
            raise TaskDescriptorError("invalid base_branch")
        if not values["publish_branch"].startswith("codex/") or not BRANCH_RE.fullmatch(
            values["publish_branch"]
        ):
            raise TaskDescriptorError("publish_branch must be a valid codex/* branch")
        if not SHA_RE.fullmatch(values["expected_base_sha"]):
            raise TaskDescriptorError("expected_base_sha must be a 40-character lowercase SHA")

        allowed_files = _string_list(data, "allowed_files")
        forbidden_patterns = _string_list(data, "forbidden_patterns")
        required_changes = _string_list(data, "required_changes")
        _string_list(data, "stop_conditions")

        session_limit = _positive_int_or_zero(data.get("session_limit"), "session_limit")
        automatic_second_session = _positive_int_or_zero(
            data.get("automatic_second_session"), "automatic_second_session"
        )
        recovery_generation = _positive_int_or_zero(
            data.get("recovery_generation", 0), "recovery_generation"
        )
        max_recovery_generations = _positive_int_or_zero(
            data.get("max_recovery_generations", 1), "max_recovery_generations"
        )
        if session_limit != 1:
            raise TaskDescriptorError("session_limit must equal 1")
        if automatic_second_session != 0:
            raise TaskDescriptorError("automatic_second_session must equal 0")
        if recovery_generation > max_recovery_generations:
            raise TaskDescriptorError("recovery_generation exceeds max_recovery_generations")

        auto_merge = data.get("auto_merge")
        notify_completion = data.get("notify_completion", False)
        if not isinstance(auto_merge, bool):
            raise TaskDescriptorError("auto_merge must be boolean")
        if not isinstance(notify_completion, bool):
            raise TaskDescriptorError("notify_completion must be boolean")
        if notify_completion and not auto_merge:
            raise TaskDescriptorError("notify_completion requires auto_merge")
        if auto_merge and values["risk_class"] != "low":
            raise TaskDescriptorError("auto_merge is only allowed for risk_class=low")
        if auto_merge and len(allowed_files) > 5:
            raise TaskDescriptorError("auto_merge tasks may allow at most five files")
        if auto_merge and any(path.startswith((".github/", "docs/", "src/")) for path in allowed_files):
            raise TaskDescriptorError("auto_merge cannot modify workflows, docs or src business code")

        parent_task_id = data.get("parent_task_id")
        if parent_task_id is not None and (not isinstance(parent_task_id, str) or not parent_task_id):
            raise TaskDescriptorError("parent_task_id must be string or null")
        parent_run_id = data.get("parent_run_id")
        if parent_run_id is not None:
            parent_run_id = _positive_int_or_zero(parent_run_id, "parent_run_id")
            if parent_run_id == 0:
                raise TaskDescriptorError("parent_run_id must be positive or null")

        return cls(
            task_id=values["task_id"],
            objective=values["objective"],
            base_branch=values["base_branch"],
            publish_branch=values["publish_branch"],
            allowed_files=allowed_files,
            forbidden_patterns=forbidden_patterns,
            required_changes=required_changes,
            gate_profile=values["gate_profile"],
            full_gate_profile=values["full_gate_profile"],
            post_merge_profile=values["post_merge_profile"],
            reasoning_effort=values["reasoning_effort"],
            session_limit=session_limit,
            automatic_second_session=automatic_second_session,
            recovery_generation=recovery_generation,
            max_recovery_generations=max_recovery_generations,
            risk_class=values["risk_class"],
            auto_merge=auto_merge,
            notify_completion=notify_completion,
            expected_base_sha=values["expected_base_sha"],
            parent_task_id=parent_task_id,
            parent_run_id=parent_run_id,
        )


def load_task_descriptor(path: Path) -> tuple[dict[str, Any], TaskDescriptor]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskDescriptorError(f"cannot load task descriptor: {path}") from exc
    if not isinstance(value, dict):
        raise TaskDescriptorError("task descriptor root must be an object")
    return value, TaskDescriptor.from_mapping(value)
