from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from branch_gc import plan_deletions  # noqa: E402
from change_impact import classify_paths  # noqa: E402
from codex_eligibility import evaluate  # noqa: E402
from execution_router import route_failure  # noqa: E402
from state_model import TaskState  # noqa: E402
from task_descriptor import TaskDescriptor, TaskDescriptorError  # noqa: E402
from upgrade_compatibility import run_matrix  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _descriptor(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = tmp_path / "module.py"
    test = tmp_path / "test_module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test.write_text("def test_value(): assert True\n", encoding="utf-8")
    value: dict[str, object] = {
        "schema_version": 2,
        "task_id": "local-product-fix",
        "objective": "Fix a reproduced local product defect.",
        "base_branch": "main",
        "publish_branch": "codex/local-product-fix",
        "allowed_files": [source.name, test.name],
        "forbidden_patterns": [".github/**", ".devflow/**", "docs/**"],
        "required_changes": ["Fix the defect", "Add regression coverage"],
        "acceptance_notes": ["One session only"],
        "gate_profile": "resilient-command-targeted",
        "full_gate_profile": "repository-full",
        "post_merge_profile": "repository-full",
        "reasoning_effort": "xhigh",
        "context_budget": {
            "max_allowed_files": 5,
            "max_task_bytes": 32768,
            "max_total_allowed_file_bytes": 262144,
            "max_single_file_bytes": 131072,
            "max_log_excerpt_lines": 300,
            "include_chat_history": False,
            "include_full_sop": False,
        },
        "failure_context": {
            "source_run_id": 123,
            "source_commit_sha": "a" * 40,
            "failure_fingerprint": "fp-local-product",
            "diagnostic_artifact_digest": "sha256:" + "b" * 64,
            "failure_files": [source.name, test.name],
            "pre_model_gate_profile": "resilient-command-targeted",
        },
        "authorization_id": "approval-local-product",
        "session_limit": 1,
        "automatic_second_session": 0,
        "recovery_generation": 0,
        "max_recovery_generations": 0,
        "parent_task_id": None,
        "parent_run_id": None,
        "risk_class": "low",
        "auto_merge": False,
        "notify_completion": False,
        "expected_base_sha": "a" * 40,
        "stop_conditions": ["scope expansion"],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def _approval(task_path: Path, tmp_path: Path) -> Path:
    now = datetime(2026, 7, 23, tzinfo=UTC)
    digest = "sha256:" + hashlib.sha256(task_path.read_bytes()).hexdigest()
    value = {
        "schema_version": 1,
        "approval_id": "approval-local-product",
        "task_id": "local-product-fix",
        "approved_by": "tyxq428",
        "approval_source": "chatgpt_web",
        "descriptor_sha256": digest,
        "failure_fingerprint": "fp-local-product",
        "max_calls": 1,
        "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _eligibility_files(tmp_path: Path, *, enabled: bool) -> tuple[Path, Path, Path]:
    policy = json.loads((REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8"))
    policy["mode"] = "enabled" if enabled else "disabled"
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text('{"schema_version":1,"entries":[]}', encoding="utf-8")
    reproduction_path = tmp_path / "reproduction.json"
    reproduction_path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "failure_fingerprint": "fp-local-product",
                "failure_files": ["module.py", "test_module.py"],
            }
        ),
        encoding="utf-8",
    )
    return policy_path, ledger_path, reproduction_path


def test_repository_codex_policy_is_disabled_and_model_action_absent() -> None:
    policy = json.loads((REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8"))
    action = (REPO / ".github/actions/codex-thin-worker/action.yml").read_text(encoding="utf-8")
    assert policy["mode"] == "disabled"
    assert policy["auto_recovery_dispatch"] is False
    assert policy["retry_failed_codex_job"] is False
    assert "openai/codex-action@" not in action
    assert "CODEX_POLICY_DISABLED" in action


def test_change_impact_preserves_github_leading_dot() -> None:
    result = classify_paths([".github/workflows/test.yml"])
    assert result.impact == "devflow_only"
    assert result.changed_files == (".github/workflows/test.yml",)


def test_unknown_and_mixed_product_paths_fail_conservatively() -> None:
    result = classify_paths(["README.md", "src/ashare_f10/api/app.py"])
    assert result.impact == "product"
    assert result.run_full_test is True
    assert result.run_e2e is True


def test_execution_router_excludes_framework_and_mechanical_failures() -> None:
    assert route_failure("RUFF_IMPORT_SORT", ["tests/test_x.py"]).route == "DETERMINISTIC_REPAIR"
    assert route_failure("STATE_CONSISTENCY", ["scripts/devflow/state_model.py"]).route == "CHATGPT_WEB"
    assert route_failure("LOCAL_PRODUCT_CODE", ["src/x.py", "tests/test_x.py"]).codex_candidate is True


def test_global_disabled_policy_rejects_otherwise_valid_task(tmp_path: Path) -> None:
    task_path, _ = _descriptor(tmp_path)
    approval = _approval(task_path, tmp_path)
    policy, ledger, reproduction = _eligibility_files(tmp_path, enabled=False)
    decision = evaluate(
        repo=tmp_path,
        task_file=task_path,
        policy_file=policy,
        approval_file=approval,
        ledger_file=ledger,
        reproduction_file=reproduction,
        actor="tyxq428",
        now=datetime(2026, 7, 23, 0, 30, tzinfo=UTC),
    )
    assert decision.codex_allowed is False
    assert "CODEX_POLICY_DISABLED" in decision.errors


def test_valid_explicit_approval_can_pass_only_when_policy_enabled(tmp_path: Path) -> None:
    task_path, _ = _descriptor(tmp_path)
    approval = _approval(task_path, tmp_path)
    policy, ledger, reproduction = _eligibility_files(tmp_path, enabled=True)
    decision = evaluate(
        repo=tmp_path,
        task_file=task_path,
        policy_file=policy,
        approval_file=approval,
        ledger_file=ledger,
        reproduction_file=reproduction,
        actor="tyxq428",
        now=datetime(2026, 7, 23, 0, 30, tzinfo=UTC),
    )
    assert decision.codex_allowed is True
    assert decision.route == "CODEX"


def test_bot_duplicate_and_nonreproducible_paths_are_rejected(tmp_path: Path) -> None:
    task_path, _ = _descriptor(tmp_path)
    approval = _approval(task_path, tmp_path)
    policy, ledger, reproduction = _eligibility_files(tmp_path, enabled=True)
    Path(ledger).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "task_id": "local-product-fix",
                        "failure_fingerprint": "fp-local-product",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    Path(reproduction).write_text(
        json.dumps(
            {
                "status": "PASS",
                "failure_fingerprint": "fp-local-product",
                "failure_files": ["module.py", "test_module.py"],
            }
        ),
        encoding="utf-8",
    )
    decision = evaluate(
        repo=tmp_path,
        task_file=task_path,
        policy_file=policy,
        approval_file=approval,
        ledger_file=ledger,
        reproduction_file=reproduction,
        actor="github-actions[bot]",
        now=datetime(2026, 7, 23, 0, 30, tzinfo=UTC),
    )
    assert decision.codex_allowed is False
    assert "BOT_DISPATCH_FORBIDDEN" in decision.errors
    assert "FAILURE_NOT_REPRODUCIBLE" in decision.errors
    assert "FINGERPRINT_ALREADY_USED" in decision.errors


def test_historical_ten_waste_runs_are_never_codex_candidates() -> None:
    fixture = json.loads(
        (REPO / "tests/fixtures/devflow/codex-waste-runs.json").read_text(encoding="utf-8")
    )
    assert len(fixture["runs"]) == 10
    for run in fixture["runs"]:
        assert run["source_workflow"] == "Devflow State Consistency"
        assert run["codex_status"] == "BLOCKED"
        assert run["changed_files_count"] == 0
        decision = route_failure("STATE_CONSISTENCY", ["scripts/devflow/state_model.py"])
        assert decision.route == "CHATGPT_WEB"
        assert decision.codex_candidate is False


def test_state_schema_v2_separates_execution_acceptance_and_security() -> None:
    value = json.loads(
        (REPO / "tests/fixtures/devflow/state-v2-running.json").read_text(encoding="utf-8")
    )
    value["execution_status"] = "COMPLETED"
    value["acceptance"]["status"] = "REVIEW_REQUIRED"
    value["acceptance"]["reason_code"] = "SOURCE_CONFLICT"
    state = TaskState.from_mapping(value)
    assert state.execution_status == "COMPLETED"
    assert state.acceptance_status == "REVIEW_REQUIRED"
    assert state.security_status == "PENDING"


def test_schema_v2_rejects_low_and_upgrade_matrix_passes() -> None:
    low = json.loads(
        (REPO / "tests/fixtures/devflow/descriptor-v2-low-invalid.json").read_text(encoding="utf-8")
    )
    with pytest.raises(TaskDescriptorError, match="must be xhigh"):
        TaskDescriptor.from_mapping(low)
    result = run_matrix(REPO / "tests/fixtures/devflow")
    assert result["status"] == "PASS"


def test_branch_gc_is_dry_run_and_fail_closed() -> None:
    decisions = plan_deletions(
        ["main", "feature/user-work", "task/codex-old", "codex/open"],
        default_branch="main",
        active_branches=set(),
        open_pr_heads={"codex/open"},
        merge_verified=True,
    )
    by_branch = {item.branch: item for item in decisions}
    assert by_branch["main"].action == "KEEP"
    assert by_branch["feature/user-work"].action == "KEEP"
    assert by_branch["codex/open"].action == "KEEP"
    assert by_branch["task/codex-old"].action == "DELETE"
