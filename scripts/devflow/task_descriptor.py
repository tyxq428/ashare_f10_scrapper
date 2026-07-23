from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA_VERSIONS = {1, 2}
LEGACY_REASONING_EFFORTS = {"low", "xhigh"}
RUNTIME_REASONING_EFFORT = "xhigh"
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RISK_CLASSES = {"low", "medium", "high"}

DEFAULT_CONTEXT_BUDGET = {
    "max_allowed_files": 5,
    "max_task_bytes": 32_768,
    "max_total_allowed_file_bytes": 262_144,
    "max_single_file_bytes": 131_072,
    "max_log_excerpt_lines": 300,
    "include_chat_history": False,
    "include_full_sop": False,
}


class TaskDescriptorError(ValueError):
    pass


def _positive_int_or_zero(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TaskDescriptorError(f"{field} must be a non-negative integer")
    return value


def _positive_int(value: object, field: str) -> int:
    result = _positive_int_or_zero(value, field)
    if result == 0:
        raise TaskDescriptorError(f"{field} must be positive")
    return result


def _string_list(
    data: dict[str, Any],
    field: str,
    *,
    non_empty: bool = True,
) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TaskDescriptorError(f"{field} must be a string array")
    if non_empty and not value:
        raise TaskDescriptorError(f"{field} must not be empty")
    return tuple(item.strip() for item in value)


@dataclass(frozen=True)
class ContextBudget:
    max_allowed_files: int
    max_task_bytes: int
    max_total_allowed_file_bytes: int
    max_single_file_bytes: int
    max_log_excerpt_lines: int
    include_chat_history: bool
    include_full_sop: bool

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        require_explicit: bool = False,
    ) -> ContextBudget:
        if value is None:
            if require_explicit:
                raise TaskDescriptorError(
                    "schema_version 2 requires an explicit context_budget"
                )
            raw: dict[str, object] = dict(DEFAULT_CONTEXT_BUDGET)
        elif isinstance(value, dict):
            unknown = sorted(set(value) - set(DEFAULT_CONTEXT_BUDGET))
            if unknown:
                raise TaskDescriptorError(
                    f"unknown context_budget field(s): {', '.join(unknown)}"
                )
            raw = {**DEFAULT_CONTEXT_BUDGET, **value}
        else:
            raise TaskDescriptorError("context_budget must be an object")

        include_chat_history = raw.get("include_chat_history")
        include_full_sop = raw.get("include_full_sop")
        if not isinstance(include_chat_history, bool):
            raise TaskDescriptorError(
                "context_budget.include_chat_history must be boolean"
            )
        if not isinstance(include_full_sop, bool):
            raise TaskDescriptorError(
                "context_budget.include_full_sop must be boolean"
            )
        if include_chat_history:
            raise TaskDescriptorError(
                "context_budget.include_chat_history must be false"
            )
        if include_full_sop:
            raise TaskDescriptorError(
                "context_budget.include_full_sop must be false"
            )

        max_total = _positive_int(
            raw.get("max_total_allowed_file_bytes"),
            "context_budget.max_total_allowed_file_bytes",
        )
        max_single = _positive_int(
            raw.get("max_single_file_bytes"),
            "context_budget.max_single_file_bytes",
        )
        if max_single > max_total:
            raise TaskDescriptorError(
                "context_budget.max_single_file_bytes cannot exceed "
                "max_total_allowed_file_bytes"
            )

        return cls(
            max_allowed_files=_positive_int(
                raw.get("max_allowed_files"),
                "context_budget.max_allowed_files",
            ),
            max_task_bytes=_positive_int(
                raw.get("max_task_bytes"),
                "context_budget.max_task_bytes",
            ),
            max_total_allowed_file_bytes=max_total,
            max_single_file_bytes=max_single,
            max_log_excerpt_lines=_positive_int(
                raw.get("max_log_excerpt_lines"),
                "context_budget.max_log_excerpt_lines",
            ),
            include_chat_history=include_chat_history,
            include_full_sop=include_full_sop,
        )


@dataclass(frozen=True)
class TaskDescriptor:
    schema_version: int
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
    context_budget: ContextBudget
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

    @property
    def effective_reasoning_effort(self) -> str:
        """Return the versioned runtime policy, never legacy metadata."""

        return RUNTIME_REASONING_EFFORT

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> TaskDescriptor:
        schema_version = data.get("schema_version")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version not in SUPPORTED_SCHEMA_VERSIONS
        ):
            raise TaskDescriptorError(
                f"unsupported schema_version: {schema_version!r}"
            )

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
                raise TaskDescriptorError(
                    f"{field} must be a non-empty string"
                )
            values[field] = value.strip()

        effort = values["reasoning_effort"]
        if schema_version == 1:
            if effort not in LEGACY_REASONING_EFFORTS:
                raise TaskDescriptorError(
                    "schema_version 1 reasoning_effort must be xhigh "
                    "or legacy low"
                )
        elif effort != RUNTIME_REASONING_EFFORT:
            raise TaskDescriptorError(
                "schema_version 2 reasoning_effort must be xhigh"
            )

        if values["risk_class"] not in RISK_CLASSES:
            raise TaskDescriptorError(
                "risk_class must be low, medium or high"
            )
        if not BRANCH_RE.fullmatch(values["base_branch"]):
            raise TaskDescriptorError("invalid base_branch")
        if (
            not values["publish_branch"].startswith("codex/")
            or not BRANCH_RE.fullmatch(values["publish_branch"])
        ):
            raise TaskDescriptorError(
                "publish_branch must be a valid codex/* branch"
            )
        if not SHA_RE.fullmatch(values["expected_base_sha"]):
            raise TaskDescriptorError(
                "expected_base_sha must be a 40-character lowercase SHA"
            )

        allowed_files = _string_list(data, "allowed_files")
        forbidden_patterns = _string_list(data, "forbidden_patterns")
        required_changes = _string_list(data, "required_changes")
        _string_list(data, "stop_conditions")
        context_budget = ContextBudget.from_mapping(
            data.get("context_budget"),
            require_explicit=schema_version == 2,
        )
        if len(allowed_files) > context_budget.max_allowed_files:
            raise TaskDescriptorError(
                "allowed_files exceeds context_budget.max_allowed_files"
            )

        session_limit = _positive_int_or_zero(
            data.get("session_limit"),
            "session_limit",
        )
        automatic_second_session = _positive_int_or_zero(
            data.get("automatic_second_session"),
            "automatic_second_session",
        )
        recovery_generation = _positive_int_or_zero(
            data.get("recovery_generation", 0),
            "recovery_generation",
        )
        max_recovery_generations = _positive_int_or_zero(
            data.get("max_recovery_generations", 1),
            "max_recovery_generations",
        )
        if session_limit != 1:
            raise TaskDescriptorError("session_limit must equal 1")
        if automatic_second_session != 0:
            raise TaskDescriptorError(
                "automatic_second_session must equal 0"
            )
        if recovery_generation > max_recovery_generations:
            raise TaskDescriptorError(
                "recovery_generation exceeds max_recovery_generations"
            )

        auto_merge = data.get("auto_merge")
        notify_completion = data.get("notify_completion", False)
        if not isinstance(auto_merge, bool):
            raise TaskDescriptorError("auto_merge must be boolean")
        if not isinstance(notify_completion, bool):
            raise TaskDescriptorError(
                "notify_completion must be boolean"
            )
        if notify_completion and not auto_merge:
            raise TaskDescriptorError(
                "notify_completion requires auto_merge"
            )
        if auto_merge and values["risk_class"] != "low":
            raise TaskDescriptorError(
                "auto_merge is only allowed for risk_class=low"
            )
        if auto_merge and len(allowed_files) > 5:
            raise TaskDescriptorError(
                "auto_merge tasks may allow at most five files"
            )
        if auto_merge and any(
            path.startswith((".github/", "docs/", "src/"))
            for path in allowed_files
        ):
            raise TaskDescriptorError(
                "auto_merge cannot modify workflows, docs or src business code"
            )

        parent_task_id = data.get("parent_task_id")
        if parent_task_id is not None and (
            not isinstance(parent_task_id, str) or not parent_task_id
        ):
            raise TaskDescriptorError(
                "parent_task_id must be string or null"
            )
        parent_run_id = data.get("parent_run_id")
        if parent_run_id is not None:
            parent_run_id = _positive_int_or_zero(
                parent_run_id,
                "parent_run_id",
            )
            if parent_run_id == 0:
                raise TaskDescriptorError(
                    "parent_run_id must be positive or null"
                )

        return cls(
            schema_version=schema_version,
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
            reasoning_effort=effort,
            context_budget=context_budget,
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


def load_task_descriptor(
    path: Path,
) -> tuple[dict[str, Any], TaskDescriptor]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskDescriptorError(
            f"cannot load task descriptor: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise TaskDescriptorError(
            "task descriptor root must be an object"
        )
    return value, TaskDescriptor.from_mapping(value)
