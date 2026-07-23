from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
if str(DEVFLOW) not in sys.path:
    sys.path.insert(0, str(DEVFLOW))

from state_model import render_handoff, render_status, validate_state_shape  # noqa: E402
from validate_state import validate_task  # noqa: E402


def base_state() -> dict:
    return {
        "schema_version": 1,
        "state_revision": 1,
        "task_id": "demo",
        "title": "Demo",
        "status": "RUNNING",
        "execution_status": "RUNNING",
        "acceptance_status": "PENDING",
        "current_stage": "W01",
        "last_completed_stage": "W00",
        "working_branch": "feature/demo",
        "delivery_base": "main",
        "pull_request": None,
        "base_sha_at_start": "abc",
        "last_product_commit_sha": "abc",
        "post_merge_gate": "PENDING",
        "human_gate": {"required": False, "reason": None, "minimum_action": None},
        "next_action": "continue",
        "recovery_entry": "docs/implementation/demo/HANDOFF.md",
        "notification_generation": 0,
        "updated_at_utc": "2026-07-23T00:00:00Z",
    }


def materialize_task(tmp_path: Path, state: dict) -> tuple[Path, dict]:
    task_dir = tmp_path / "docs" / "implementation" / "demo"
    task_dir.mkdir(parents=True)
    (task_dir / "task_state.yaml").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    for name in ("00_contract.md", "01_master_plan.md", "W00_plan.md", "W00_result.md"):
        (task_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    (task_dir / f"{state['current_stage']}_plan.md").write_text("# plan\n", encoding="utf-8")
    (task_dir / "STATUS.md").write_text(render_status(state), encoding="utf-8")
    (task_dir / "HANDOFF.md").write_text(render_handoff(state), encoding="utf-8")
    entry = {
        "task_id": "demo",
        "title": "Demo",
        "status": state["status"],
        "branch": state["working_branch"],
        "pull_request": state["pull_request"],
        "state_file": "docs/implementation/demo/task_state.yaml",
    }
    return task_dir, entry


def test_valid_task_and_generated_docs(tmp_path: Path) -> None:
    state = base_state()
    _, entry = materialize_task(tmp_path, state)
    assert validate_task(tmp_path, entry, check_generated=True, check_git=False) == []


def test_result_without_plan_fails(tmp_path: Path) -> None:
    state = base_state()
    task_dir, entry = materialize_task(tmp_path, state)
    (task_dir / "W02_result.md").write_text("# result\n", encoding="utf-8")
    errors = validate_task(tmp_path, entry, check_generated=False, check_git=False)
    assert any("W02_result.md exists without W02_plan.md" in item for item in errors)


def test_done_requires_success_acceptance_and_post_merge() -> None:
    state = base_state()
    state.update(
        {
            "status": "DONE",
            "execution_status": "SUCCESS",
            "acceptance_status": "PASS",
            "post_merge_gate": "PENDING",
            "current_stage": "W08",
            "last_completed_stage": "W08",
            "next_action": "none",
        }
    )
    errors = validate_state_shape(state)
    assert "DONE requires post_merge_gate PASS" in errors


def test_human_gate_requires_reason_and_minimum_action() -> None:
    state = base_state()
    state["status"] = "WAITING_HUMAN"
    state["human_gate"] = {"required": True, "reason": "", "minimum_action": None}
    errors = validate_state_shape(state)
    assert "human_gate.required needs a non-empty reason" in errors
    assert "human_gate.required needs a minimum_action" in errors


def test_rendering_is_deterministic() -> None:
    state = base_state()
    assert render_status(state) == render_status(deepcopy(state))
    assert render_handoff(state) == render_handoff(deepcopy(state))
