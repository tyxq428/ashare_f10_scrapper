from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from context_budget import inspect_context  # noqa: E402
from task_descriptor import TaskDescriptor, TaskDescriptorError  # noqa: E402


def task_mapping(*, effort: str = "xhigh", context_budget: dict[str, object] | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 1,
        "task_id": "context-budget-test",
        "objective": "Make one bounded change.",
        "base_branch": "main",
        "publish_branch": "codex/context-budget-test",
        "allowed_files": ["src/example.py", "tests/test_example.py"],
        "forbidden_patterns": [".github/**", ".env", "secrets/**", "docs/**"],
        "required_changes": ["Keep the patch bounded."],
        "acceptance_notes": ["Use deterministic tests."],
        "gate_profile": "resilient-command-targeted",
        "full_gate_profile": "repository-full",
        "post_merge_profile": "repository-full",
        "reasoning_effort": effort,
        "session_limit": 1,
        "automatic_second_session": 0,
        "recovery_generation": 0,
        "max_recovery_generations": 1,
        "parent_task_id": None,
        "parent_run_id": None,
        "risk_class": "low",
        "auto_merge": False,
        "notify_completion": False,
        "expected_base_sha": "a" * 40,
        "stop_conditions": ["context budget violation"],
    }
    if context_budget is not None:
        value["context_budget"] = context_budget
    return value


def test_new_descriptor_defaults_to_bounded_context() -> None:
    task = TaskDescriptor.from_mapping(task_mapping())
    assert task.reasoning_effort == "xhigh"
    assert task.context_budget.max_allowed_files == 5
    assert task.context_budget.include_chat_history is False
    assert task.context_budget.include_full_sop is False


def test_legacy_low_descriptor_is_readable_but_does_not_define_runtime_effort() -> None:
    task = TaskDescriptor.from_mapping(task_mapping(effort="low"))
    assert task.reasoning_effort == "low"
    assert task.context_budget.max_task_bytes == 32768


def test_context_budget_rejects_chat_history_and_full_sop() -> None:
    for field in ("include_chat_history", "include_full_sop"):
        budget = {field: True}
        with pytest.raises(TaskDescriptorError, match=field):
            TaskDescriptor.from_mapping(task_mapping(context_budget=budget))


def test_context_budget_rejects_too_many_declared_files() -> None:
    value = task_mapping(context_budget={"max_allowed_files": 1})
    with pytest.raises(TaskDescriptorError, match="max_allowed_files"):
        TaskDescriptor.from_mapping(value)


def test_context_budget_passes_for_small_existing_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/example.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests/test_example.py").write_text("def test_value(): pass\n", encoding="utf-8")
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(task_mapping()), encoding="utf-8")
    task = TaskDescriptor.from_mapping(task_mapping())

    result = inspect_context(tmp_path, task_file, task)

    assert result.status == "PASS"
    assert result.total_existing_file_bytes > 0
    assert result.violations == ()


def test_context_budget_fails_before_model_call_for_large_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/example.py").write_bytes(b"x" * 32)
    (tmp_path / "tests/test_example.py").write_text("pass\n", encoding="utf-8")
    value = task_mapping(
        context_budget={
            "max_single_file_bytes": 16,
            "max_total_allowed_file_bytes": 64,
        }
    )
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(value), encoding="utf-8")
    task = TaskDescriptor.from_mapping(value)

    result = inspect_context(tmp_path, task_file, task)

    assert result.status == "FAIL"
    assert "SINGLE_FILE_TOO_LARGE:src/example.py" in result.violations
