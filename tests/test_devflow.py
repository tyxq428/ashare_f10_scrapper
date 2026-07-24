from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from endpoint_utils import normalize_responses_endpoint  # noqa: E402
from finalize_task import finalize  # noqa: E402
from gate_profiles import get_gate_profile  # noqa: E402
from private_responses_forwarder import run_server  # noqa: E402
from recovery_policy import classify  # noqa: E402
from runtime_preflight import inspect_runtime  # noqa: E402
from secret_audit import secret_variants  # noqa: E402
from state_model import StateError, TaskState, load_json_yaml  # noqa: E402
from task_descriptor import TaskDescriptor, TaskDescriptorError  # noqa: E402
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


def valid_task() -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": "sample-fix",
        "objective": "Fix one deterministic bug.",
        "base_branch": "main",
        "publish_branch": "codex/sample-fix",
        "allowed_files": ["scripts/example.py", "tests/test_example.py"],
        "forbidden_patterns": [".github/**", ".env", "secrets/**", "docs/**"],
        "required_changes": ["Fix the bug", "Add regression coverage"],
        "acceptance_notes": ["Keep the patch minimal"],
        "gate_profile": "resilient-command-targeted",
        "full_gate_profile": "repository-full",
        "post_merge_profile": "repository-full",
        "reasoning_effort": "low",
        "session_limit": 1,
        "automatic_second_session": 0,
        "recovery_generation": 0,
        "max_recovery_generations": 1,
        "parent_task_id": None,
        "parent_run_id": None,
        "risk_class": "low",
        "auto_merge": True,
        "notify_completion": True,
        "expected_base_sha": "b" * 40,
        "stop_conditions": [
            "any changed path outside allowed_files",
            "secret audit match",
            "business decision required",
        ],
    }


def failed_jobs(step_name: str, conclusion: str = "failure") -> dict[str, object]:
    return {
        "jobs": [
            {
                "name": "job",
                "steps": [
                    {"name": "Set up job", "conclusion": "success"},
                    {"name": step_name, "conclusion": conclusion},
                ],
            }
        ]
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
    data.update(
        {
            "status": "DONE",
            "execution_status": "COMPLETED",
            "research_acceptance_status": "PASS",
            "last_completed_stage": "W01",
        }
    )
    with pytest.raises(StateError, match="post_merge PASS"):
        TaskState.from_mapping(data)


def test_done_requires_current_stage_to_be_completed() -> None:
    data = valid_state()
    data.update(
        {
            "status": "DONE",
            "execution_status": "COMPLETED",
            "research_acceptance_status": "PASS",
            "last_completed_stage": "W00",
        }
    )
    post_merge = data["post_merge"]
    assert isinstance(post_merge, dict)
    post_merge["status"] = "PASS"
    with pytest.raises(StateError, match="equal current_stage"):
        TaskState.from_mapping(data)


def test_done_accepts_current_stage_as_last_completed() -> None:
    data = valid_state()
    data.update(
        {
            "status": "DONE",
            "execution_status": "COMPLETED",
            "research_acceptance_status": "PASS",
            "last_completed_stage": "W01",
        }
    )
    post_merge = data["post_merge"]
    assert isinstance(post_merge, dict)
    post_merge["status"] = "PASS"
    assert TaskState.from_mapping(data).status == "DONE"


def test_human_gate_requires_minimum_action_and_resume() -> None:
    data = valid_state()
    data["status"] = "WAITING_HUMAN"
    data["human_gate"] = {
        "required": True,
        "reason": "permission",
        "minimum_action": None,
        "resume_from": None,
    }
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


def test_task_descriptor_accepts_explicit_low_risk_auto_merge() -> None:
    task = TaskDescriptor.from_mapping(valid_task())
    assert task.auto_merge is True
    assert task.notify_completion is True
    assert task.full_gate_profile == "repository-full"


def test_task_descriptor_rejects_high_risk_auto_merge() -> None:
    data = valid_task()
    data["risk_class"] = "high"
    with pytest.raises(TaskDescriptorError, match="risk_class=low"):
        TaskDescriptor.from_mapping(data)


def test_task_descriptor_rejects_workflow_or_docs_auto_merge_scope() -> None:
    for path in (".github/workflows/x.yml", "docs/x.md", "src/module.py"):
        data = valid_task()
        data["allowed_files"] = [path]
        with pytest.raises(TaskDescriptorError, match="cannot modify"):
            TaskDescriptor.from_mapping(data)


def test_notify_completion_requires_auto_merge() -> None:
    data = valid_task()
    data["auto_merge"] = False
    with pytest.raises(TaskDescriptorError, match="requires auto_merge"):
        TaskDescriptor.from_mapping(data)


def test_pre_model_infrastructure_failure_retries_silently() -> None:
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=101,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert decision.action == "RETRY"
    assert decision.notification_type is None


def test_codex_checkout_failure_is_never_automatically_rerun() -> None:
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=101,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"


def test_codex_failure_never_reruns_automatically() -> None:
    first = classify(
        source_workflow="Codex Task",
        source_run_id=102,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run one Codex Thin Worker session"),
    )
    second = classify(
        source_workflow="Codex Task",
        source_run_id=102,
        conclusion="failure",
        run_attempt=2,
        jobs_payload=failed_jobs("Run one Codex Thin Worker session"),
    )
    assert first.action == "INTERRUPTED"
    assert first.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"
    assert first.notification_type == "INTERRUPTED"
    assert second.action == "INTERRUPTED"
    assert second.reason_code == "CODEX_SESSION_NO_AUTOMATIC_RETRY"


def test_missing_agent_runtime_secrets_are_a_real_human_gate(tmp_path: Path) -> None:
    (tmp_path / "runtime-preflight.json").write_text(
        json.dumps(
            {
                "status": "FAIL",
                "failure_codes": ["MISSING_ENDPOINT", "MISSING_API_KEY", "MISSING_MODEL"],
            }
        ),
        encoding="utf-8",
    )
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=103,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Validate runtime configuration without exposing values"),
        artifact_root=tmp_path,
    )
    assert decision.action == "HUMAN_REQUIRED"
    assert decision.reason_code == "AGENT_RUNTIME_SECRETS_MISSING"


def test_secret_or_scope_failure_is_security_blocked(tmp_path: Path) -> None:
    (tmp_path / "secret-audit.json").write_text('{"status":"FAIL"}', encoding="utf-8")
    decision = classify(
        source_workflow="Devflow Secret Audit",
        source_run_id=104,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Secret audit"),
        artifact_root=tmp_path,
    )
    assert decision.action == "SECURITY_BLOCKED"
    assert decision.notification_type == "SECURITY_BLOCKED"


def test_state_consistency_failure_never_creates_automatic_codex_repair(
    tmp_path: Path,
) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(valid_task()), encoding="utf-8")
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=105,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Validate devflow workflows and tests"),
        task_file=task_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED"
    assert decision.notification_type == "INTERRUPTED"


def test_recovery_generation_is_effectively_zero_and_generator_removed() -> None:
    task = TaskDescriptor.from_mapping(valid_task())
    assert task.recovery_generation == 0
    assert task.max_recovery_generations == 0
    assert not (DEVFLOW / "recovery_task.py").exists()


def test_failure_fingerprint_is_stable_for_same_root_cause() -> None:
    one = classify(
        source_workflow="Codex Task",
        source_run_id=301,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    two = classify(
        source_workflow="Codex Task",
        source_run_id=999,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Run actions/checkout@sha"),
    )
    assert one.fingerprint == two.fingerprint


def test_finalizer_closes_state_and_generates_final_report(tmp_path: Path) -> None:
    repo = tmp_path
    task_dir = repo / "docs/implementation/chatgpt-web-codex-devflow-v1"
    task_dir.mkdir(parents=True)
    data = valid_state()
    data.update(
        {
            "task_id": "chatgpt-web-codex-devflow-v1",
            "title": "Devflow",
            "working_branch": "main",
            "pull_request": 30,
            "current_stage": "W05",
            "last_completed_stage": "W04",
        }
    )
    notification = data["notification"]
    assert isinstance(notification, dict)
    notification["control_issue_number"] = 32
    (task_dir / "task_state.yaml").write_text(json.dumps(data), encoding="utf-8")
    for name in ("00_contract.md", "01_master_plan.md", "STATUS.md", "HANDOFF.md", "DECISIONS.md"):
        (task_dir / name).write_text("placeholder\n", encoding="utf-8")
    for number in range(9):
        stage = f"W{number:02d}"
        (task_dir / f"{stage}_plan.md").write_text("plan\n", encoding="utf-8")
        if number <= 4:
            (task_dir / f"{stage}_result.md").write_text("result\n", encoding="utf-8")
    active_path = repo / "docs/implementation/ACTIVE_TASKS.yaml"
    active_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": [
                    {
                        "task_id": "chatgpt-web-codex-devflow-v1",
                        "status": "RUNNING",
                        "branch": "main",
                        "current_stage": "W05",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = finalize(
        repo=repo,
        task_dir=task_dir,
        product_sha="d" * 40,
        post_merge_run_id=400,
        thin_slice_task_id="thin-slice",
        source_product_gate_run_id=399,
    )
    assert result["status"] == "DONE"
    assert result["last_completed_stage"] == "W08"
    assert (task_dir / "FINAL_REPORT.md").is_file()
    assert TaskState.from_mapping(load_json_yaml(task_dir / "task_state.yaml")).status == "DONE"


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


def test_codex_blocked_result_never_retries(tmp_path: Path) -> None:
    (tmp_path / "codex-result.json").write_text(
        json.dumps(
            {
                "status": "BLOCKED",
                "changed_files": [],
                "tests_passed": False,
                "blocking_reason": "scope unavailable",
            }
        ),
        encoding="utf-8",
    )
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=1001,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Enforce runtime, Codex, scope, gate and secret outcomes"),
        artifact_root=tmp_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_BLOCKED_NO_RETRY"
    assert decision.notification_type == "INTERRUPTED"


def test_state_consistency_failure_requires_web_supervisor_not_codex() -> None:
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=1002,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Validate devflow workflows and tests"),
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED"
    assert decision.notification_type == "INTERRUPTED"
