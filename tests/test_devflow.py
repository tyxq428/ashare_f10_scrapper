from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from endpoint_utils import normalize_responses_endpoint  # noqa: E402
from gate_profiles import get_gate_profile  # noqa: E402
from private_responses_forwarder import run_server  # noqa: E402
from runtime_preflight import inspect_runtime  # noqa: E402
from secret_audit import secret_variants  # noqa: E402
from state_model import StateError, TaskState, load_json_yaml  # noqa: E402
from validate_state import branch_matches_state  # noqa: E402
from validate_workflows import validate_file  # noqa: E402
from verify_changed_paths import verify  # noqa: E402


def valid_state() -> dict[str, object]:
    return {
        "schema_version": 1,
        "state_revision": 1,
        "task_id": "sample",
        "title": "Sample",
        "status": "RUNNING",
        "execution_status": "RUNNING",
        "research_acceptance_status": "PENDING",
        "working_branch": "feature/sample",
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
        "human_gate": {"required": False, "reason": None, "minimum_action": None, "resume_from": None},
        "post_merge": {"status": "PENDING", "merge_sha": None, "verified_run_ids": []},
        "notification": {
            "generation": 0,
            "last_type": None,
            "acknowledged": True,
            "control_issue_number": None,
        },
        "updated_at_utc": "2026-07-23T00:00:00Z",
    }


def test_state_accepts_execution_and_research_status_separately() -> None:
    data = valid_state()
    data["execution_status"] = "COMPLETED"
    data["research_acceptance_status"] = "REVIEW_REQUIRED"
    state = TaskState.from_mapping(data)
    assert state.execution_status == "COMPLETED"
    assert state.research_acceptance_status == "REVIEW_REQUIRED"


def test_state_exposes_pull_request_and_control_issue() -> None:
    data = valid_state()
    data["pull_request"] = 30
    notification = data["notification"]
    assert isinstance(notification, dict)
    notification["control_issue_number"] = 32
    state = TaskState.from_mapping(data)
    assert state.pull_request == 30
    assert state.control_issue_number == 32


@pytest.mark.parametrize("value", [0, -1, True, "30"])
def test_pull_request_must_be_a_positive_integer_or_null(value: object) -> None:
    data = valid_state()
    data["pull_request"] = value
    with pytest.raises(StateError, match="positive integer or null"):
        TaskState.from_mapping(data)


@pytest.mark.parametrize("value", [0, -1, True, "32"])
def test_control_issue_number_must_be_a_positive_integer_or_null(value: object) -> None:
    data = valid_state()
    notification = data["notification"]
    assert isinstance(notification, dict)
    notification["control_issue_number"] = value
    with pytest.raises(StateError, match="positive integer or null"):
        TaskState.from_mapping(data)


def test_done_requires_post_merge_pass() -> None:
    data = valid_state()
    data.update({"status": "DONE", "execution_status": "COMPLETED"})
    with pytest.raises(StateError, match="post_merge PASS"):
        TaskState.from_mapping(data)


def test_human_gate_requires_minimum_action_and_resume() -> None:
    data = valid_state()
    data["status"] = "WAITING_HUMAN"
    data["human_gate"] = {"required": True, "reason": "permission", "minimum_action": None, "resume_from": None}
    with pytest.raises(StateError, match="minimum_action"):
        TaskState.from_mapping(data)


def test_json_is_valid_yaml_subset_state_format(tmp_path: Path) -> None:
    path = tmp_path / "task_state.yaml"
    path.write_text(json.dumps(valid_state()), encoding="utf-8")
    assert load_json_yaml(path)["task_id"] == "sample"


def test_working_branch_is_required_before_merge() -> None:
    state = TaskState.from_mapping(valid_state())
    assert branch_matches_state("feature/sample", state) is True
    assert branch_matches_state("feature/other", state) is False
    assert branch_matches_state("main", state) is False


def test_main_is_valid_for_merge_and_post_merge_gates() -> None:
    data = valid_state()
    data["pull_request"] = 30
    data["current_stage"] = "W05"
    state = TaskState.from_mapping(data)
    assert branch_matches_state("main", state) is True
    assert branch_matches_state("feature/other", state) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://relay.invalid", "https://relay.invalid/v1/responses"),
        ("https://relay.invalid/v1", "https://relay.invalid/v1/responses"),
        ("https://relay.invalid/v1/responses", "https://relay.invalid/v1/responses"),
    ],
)
def test_endpoint_normalization(raw: str, expected: str) -> None:
    assert normalize_responses_endpoint(raw) == expected


def test_endpoint_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        normalize_responses_endpoint("http://relay.invalid/v1")


def test_runtime_preflight_reports_only_safe_checks() -> None:
    endpoint = "https://relay.invalid/v1"
    api_key = "secret-key-value"
    model = "private-model"
    result = inspect_runtime(endpoint, api_key, model)
    assert result["status"] == "PASS"
    serialized = json.dumps(result)
    assert endpoint not in serialized
    assert api_key not in serialized
    assert model not in serialized


def test_runtime_preflight_classifies_missing_values() -> None:
    result = inspect_runtime("", "", "")
    assert result["status"] == "FAIL"
    assert set(result["failure_codes"]) == {"MISSING_ENDPOINT", "MISSING_API_KEY", "MISSING_MODEL"}


def test_forwarder_invalid_configuration_writes_safe_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENT_RESPONSES_ENDPOINT", raising=False)
    status_file = tmp_path / "status.json"
    assert run_server(0, status_file) == 2
    status = json.loads(status_file.read_text(encoding="utf-8"))
    assert status == {"failure_class": "INVALID_OR_MISSING_ENDPOINT", "status": "FAILED"}


def test_scope_guard_fails_closed() -> None:
    assert verify(["src/a.py", "tests/test_a.py"], ["src/a.py"]) == ["tests/test_a.py"]
    assert verify(["src/a.py"], ["src/*.py"]) == []


def test_unknown_gate_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown gate profile"):
        get_gate_profile("arbitrary-shell-from-user")


def test_secret_variants_include_host_and_encoded_values() -> None:
    variants = secret_variants("https://relay.invalid/v1", "secret-key-value", "model-private")
    decoded = {item.decode("utf-8") for item in variants}
    assert "relay.invalid" in decoded
    assert "secret-key-value" in decoded
    assert any("aHR0c" in item for item in decoded)


def test_workflow_policy_rejects_floating_action_and_pull_request_target(tmp_path: Path) -> None:
    workflow = tmp_path / "bad.yml"
    workflow.write_text(
        "on: pull_request_target\njobs:\n  bad:\n    steps:\n      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    errors = validate_file(workflow)
    assert any("pull_request_target" in error for error in errors)
    assert any("full SHA" in error for error in errors)
