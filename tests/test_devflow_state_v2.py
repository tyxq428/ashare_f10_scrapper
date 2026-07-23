from __future__ import annotations

import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from state_model import StateError, TaskState  # noqa: E402


def base_state_v2() -> dict[str, object]:
    return {
        "schema_version": 2,
        "state_revision": 1,
        "task_id": "generic-task",
        "title": "Generic task",
        "status": "RUNNING",
        "execution_status": "RUNNING",
        "acceptance": {
            "domain": "generic",
            "status": "PENDING",
            "reason_code": None,
            "details_path": None,
        },
        "security_status": "PENDING",
        "working_branch": "feature/generic-task",
        "pull_request": None,
        "base_sha_at_start": "a" * 40,
        "last_product_commit_sha": "a" * 40,
        "last_state_commit_sha": None,
        "current_stage": "W01",
        "last_completed_stage": "W00",
        "last_successful_step": "baseline",
        "next_action": "continue",
        "gate_results": {},
        "retry_budget": {"infrastructure": 3, "codex_sessions": 1},
        "human_gate": {
            "required": False,
            "reason": None,
            "minimum_action": None,
            "resume_from": None,
        },
        "post_merge": {"status": "PENDING", "merge_sha": None, "verified_run_ids": []},
        "notification": {
            "generation": 0,
            "last_type": None,
            "acknowledged": True,
            "control_issue_number": None,
        },
        "updated_at_utc": "2026-07-23T00:00:00Z",
    }


def legacy_state_v1() -> dict[str, object]:
    value = base_state_v2()
    value["schema_version"] = 1
    value["research_acceptance_status"] = "REVIEW_REQUIRED"
    value.pop("acceptance")
    value.pop("security_status")
    return value


def test_schema_v2_separates_platform_and_domain_state() -> None:
    state = TaskState.from_mapping(base_state_v2())
    assert state.execution_status == "RUNNING"
    assert state.acceptance_domain == "generic"
    assert state.acceptance_status == "PENDING"
    assert state.security_status == "PENDING"


def test_schema_v1_maps_research_acceptance_without_rewriting_history() -> None:
    state = TaskState.from_mapping(legacy_state_v1())
    assert state.schema_version == 1
    assert state.acceptance_domain == "research"
    assert state.acceptance_status == "REVIEW_REQUIRED"
    assert state.research_acceptance_status == "REVIEW_REQUIRED"


def test_source_conflict_can_complete_execution_without_being_program_failure() -> None:
    value = base_state_v2()
    value["execution_status"] = "COMPLETED"
    value["acceptance"] = {
        "domain": "research",
        "status": "REVIEW_REQUIRED",
        "reason_code": "SOURCE_CONFLICT",
        "details_path": "artifacts/conflicts.json",
    }
    state = TaskState.from_mapping(value)
    assert state.execution_status == "COMPLETED"
    assert state.acceptance_status == "REVIEW_REQUIRED"


def test_done_requires_generic_acceptance_security_and_post_merge_pass() -> None:
    value = base_state_v2()
    value.update(
        {
            "status": "DONE",
            "execution_status": "COMPLETED",
            "acceptance": {"domain": "generic", "status": "PASS"},
            "security_status": "PASS",
            "current_stage": "W01",
            "last_completed_stage": "W01",
            "post_merge": {"status": "PASS", "merge_sha": "b" * 40, "verified_run_ids": [1]},
        }
    )
    assert TaskState.from_mapping(value).status == "DONE"

    value["security_status"] = "BLOCKED"
    with pytest.raises(StateError, match="security_status PASS"):
        TaskState.from_mapping(value)


def test_unknown_state_schema_fails_closed() -> None:
    value = base_state_v2()
    value["schema_version"] = 99
    with pytest.raises(StateError, match="unsupported schema_version"):
        TaskState.from_mapping(value)
