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
from codex_policy import (  # noqa: E402
    CodexGrant,
    CodexPolicyError,
    allowed_files_hash,
    consume_reservation,
    reserve_grant,
)
from execution_router import route_failure  # noqa: E402
from state_model import TaskState  # noqa: E402
from task_descriptor import TaskDescriptor, TaskDescriptorError  # noqa: E402
from trusted_reproduction import load_trusted_reproduction  # noqa: E402
from upgrade_compatibility import run_matrix  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CONTROL_SHA = "c" * 40
TASK_SHA = "d" * 40
SOURCE_SHA = "a" * 40
ARTIFACT_DIGEST = "sha256:" + "b" * 64


def _assessment() -> dict[str, object]:
    return {
        "attempted": True,
        "can_complete_in_web": False,
        "reason_code": "LOCAL_ITERATIVE_TOOL_LOOP",
        "summary": "The bounded task needs a runner-side iterative tool loop.",
    }


def _descriptor(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = tmp_path / "module.py"
    test = tmp_path / "test_module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test.write_text("def test_value(): assert True\n", encoding="utf-8")
    value: dict[str, object] = {
        "schema_version": 2,
        "task_id": "local-product-fix",
        "objective": "Fix a reproduced local implementation defect.",
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
            "source_commit_sha": SOURCE_SHA,
            "failure_fingerprint": "fp-local-product",
            "diagnostic_artifact_digest": ARTIFACT_DIGEST,
            "failure_files": [source.name, test.name],
            "pre_model_gate_profile": "resilient-command-targeted",
            "reason_code": "LOCAL_IMPLEMENTATION_DEFECT",
        },
        "web_resolution_assessment": _assessment(),
        "authorization_id": "grant-local-product",
        "session_limit": 1,
        "automatic_second_session": 0,
        "recovery_generation": 0,
        "max_recovery_generations": 0,
        "parent_task_id": None,
        "parent_run_id": None,
        "risk_class": "low",
        "auto_merge": False,
        "notify_completion": False,
        "expected_base_sha": SOURCE_SHA,
        "stop_conditions": ["scope expansion"],
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def _grant(task_path: Path, tmp_path: Path, *, ttl_minutes: int = 45) -> Path:
    now = datetime(2026, 7, 24, tzinfo=UTC)
    task = TaskDescriptor.from_mapping(json.loads(task_path.read_text()))
    digest = "sha256:" + hashlib.sha256(task_path.read_bytes()).hexdigest()
    value = {
        "schema_version": 1,
        "grant_id": "grant-local-product",
        "task_id": "local-product-fix",
        "approved_by": "tyxq428",
        "approval_source": "chatgpt_web",
        "descriptor_sha256": digest,
        "task_commit_sha": TASK_SHA,
        "source_run_id": 123,
        "source_commit_sha": SOURCE_SHA,
        "failure_fingerprint": "fp-local-product",
        "allowed_files_hash": allowed_files_hash(task.allowed_files),
        "max_calls": 1,
        "state": "ISSUED",
        "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(minutes=ttl_minutes))
        .isoformat()
        .replace("+00:00", "Z"),
    }
    path = tmp_path / "grant.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _evidence(tmp_path: Path) -> Path:
    value = {
        "schema_version": 1,
        "status": "FAIL",
        "generated_by": "trusted_pre_model_job",
        "control_commit_sha": CONTROL_SHA,
        "task_commit_sha": TASK_SHA,
        "source_run_id": 123,
        "source_commit_sha": SOURCE_SHA,
        "diagnostic_artifact_digest": ARTIFACT_DIGEST,
        "gate_profile": "resilient-command-targeted",
        "failure_fingerprint": "fp-local-product",
        "failure_files": ["module.py", "test_module.py"],
        "observed_at_utc": "2026-07-24T00:05:00Z",
    }
    path = tmp_path / "trusted-evidence.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _policy_and_ledger(
    tmp_path: Path, *, enabled: bool
) -> tuple[Path, Path]:
    policy = json.loads(
        (REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8")
    )
    policy["mode"] = "enabled" if enabled else "disabled"
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        '{"schema_version":2,"entries":[]}', encoding="utf-8"
    )
    return policy_path, ledger_path


def _evaluate(tmp_path: Path, *, enabled: bool = True):
    task_path, _ = _descriptor(tmp_path)
    policy, ledger = _policy_and_ledger(tmp_path, enabled=enabled)
    return evaluate(
        repo=tmp_path,
        task_file=task_path,
        policy_file=policy,
        grant_file=_grant(task_path, tmp_path),
        ledger_file=ledger,
        trusted_evidence_file=_evidence(tmp_path),
        actor="tyxq428",
        control_commit_sha=CONTROL_SHA,
        task_commit_sha=TASK_SHA,
        now=datetime(2026, 7, 24, 0, 30, tzinfo=UTC),
    )


def test_repository_codex_policy_is_disabled_and_model_action_absent() -> None:
    policy = json.loads(
        (REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8")
    )
    action = (
        REPO / ".github/actions/codex-thin-worker/action.yml"
    ).read_text(encoding="utf-8")
    assert policy["mode"] == "disabled"
    assert policy["auto_recovery_dispatch"] is False
    assert policy["retry_failed_codex_job"] is False
    assert policy["limits"]["recovery_generations"] == 0
    assert "openai/codex-action@" not in action
    assert "CODEX_POLICY_DISABLED" in action


def test_change_impact_preserves_github_leading_dot() -> None:
    result = classify_paths([".github/workflows/test.yml"])
    assert result.impact == "devflow_only"
    assert result.changed_files == (".github/workflows/test.yml",)


def test_router_uses_positive_allowlist_and_web_assessment() -> None:
    assert (
        route_failure("RUFF_IMPORT_SORT", ["tests/test_x.py"]).route
        == "DETERMINISTIC_REPAIR"
    )
    assert (
        route_failure(
            "STATE_CONSISTENCY", ["scripts/devflow/state_model.py"]
        ).route
        == "CHATGPT_WEB"
    )
    assert (
        route_failure("UNKNOWN_NEW_REASON", ["src/x.py", "tests/test_x.py"])
        .codex_candidate
        is False
    )
    assert (
        route_failure(
            "LOCAL_IMPLEMENTATION_DEFECT",
            ["src/x.py", "tests/test_x.py"],
        ).codex_candidate
        is False
    )
    assert route_failure(
        "LOCAL_IMPLEMENTATION_DEFECT",
        ["src/x.py", "tests/test_x.py"],
        web_resolution_assessment=_assessment(),
    ).codex_candidate
    assert (
        route_failure(
            "LOCAL_IMPLEMENTATION_DEFECT",
            ["src/x.py"],
            web_resolution_assessment=_assessment(),
        ).codex_candidate
        is False
    )


def test_global_disabled_policy_rejects_otherwise_valid_task(
    tmp_path: Path,
) -> None:
    decision = _evaluate(tmp_path, enabled=False)
    assert decision.codex_allowed is False
    assert "CODEX_POLICY_DISABLED" in decision.errors


def test_valid_grant_and_trusted_evidence_pass_only_when_enabled(
    tmp_path: Path,
) -> None:
    decision = _evaluate(tmp_path, enabled=True)
    assert decision.codex_allowed is True
    assert decision.route == "CODEX"


def test_bot_duplicate_and_untrusted_evidence_are_rejected(
    tmp_path: Path,
) -> None:
    task_path, _ = _descriptor(tmp_path)
    policy, ledger = _policy_and_ledger(tmp_path, enabled=True)
    Path(ledger).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "entries": [
                    {
                        "grant_id": "grant-local-product",
                        "task_id": "local-product-fix",
                        "failure_fingerprint": "fp-local-product",
                        "state": "CONSUMED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evidence = _evidence(tmp_path)
    value = json.loads(evidence.read_text(encoding="utf-8"))
    value["generated_by"] = "task_branch_self_report"
    evidence.write_text(json.dumps(value), encoding="utf-8")
    decision = evaluate(
        repo=tmp_path,
        task_file=task_path,
        policy_file=policy,
        grant_file=_grant(task_path, tmp_path),
        ledger_file=ledger,
        trusted_evidence_file=evidence,
        actor="github-actions[bot]",
        control_commit_sha=CONTROL_SHA,
        task_commit_sha=TASK_SHA,
        now=datetime(2026, 7, 24, 0, 30, tzinfo=UTC),
    )
    assert decision.codex_allowed is False
    assert "BOT_DISPATCH_FORBIDDEN" in decision.errors
    assert any(item.startswith("TRUSTED_EVIDENCE_INVALID") for item in decision.errors)
    assert "FINGERPRINT_ALREADY_USED" in decision.errors
    assert "GRANT_ALREADY_CONSUMED" in decision.errors


def test_grant_ttl_reservation_and_consumption_are_single_use(
    tmp_path: Path,
) -> None:
    task_path, _ = _descriptor(tmp_path)
    with pytest.raises(CodexPolicyError, match="TTL"):
        CodexGrant.from_mapping(
            json.loads(_grant(task_path, tmp_path, ttl_minutes=61).read_text())
        )
    grant = CodexGrant.from_mapping(
        json.loads(_grant(task_path, tmp_path).read_text())
    )
    reservation = reserve_grant(
        grant,
        [],
        run_id=999,
        reserved_at_utc="2026-07-24T00:10:00Z",
    )
    consumed = consume_reservation(
        reservation,
        consumed_at_utc="2026-07-24T00:11:00Z",
        result="TIMEOUT",
    )
    assert consumed["state"] == "CONSUMED"
    with pytest.raises(CodexPolicyError, match="GRANT_ALREADY_CONSUMED"):
        reserve_grant(
            grant,
            [consumed],
            run_id=1000,
            reserved_at_utc="2026-07-24T00:12:00Z",
        )


def test_historical_ten_waste_runs_are_never_codex_candidates() -> None:
    fixture = json.loads(
        (REPO / "tests/fixtures/devflow/codex-waste-runs.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(fixture["runs"]) == 10
    for run in fixture["runs"]:
        assert run["source_workflow"] == "Devflow State Consistency"
        assert run["codex_status"] == "BLOCKED"
        assert run["changed_files_count"] == 0
        decision = route_failure(
            "STATE_CONSISTENCY", ["scripts/devflow/state_model.py"]
        )
        assert decision.route == "CHATGPT_WEB"
        assert decision.codex_candidate is False


def test_state_schema_v2_separates_execution_acceptance_and_security() -> None:
    value = json.loads(
        (REPO / "tests/fixtures/devflow/state-v2-running.json").read_text(
            encoding="utf-8"
        )
    )
    value["execution_status"] = "COMPLETED"
    value["acceptance"]["status"] = "REVIEW_REQUIRED"
    value["acceptance"]["reason_code"] = "SOURCE_CONFLICT"
    state = TaskState.from_mapping(value)
    assert state.execution_status == "COMPLETED"
    assert state.acceptance_status == "REVIEW_REQUIRED"
    assert state.security_status == "PENDING"


def test_schema_v2_rejects_low_and_all_recovery_is_effectively_zero() -> None:
    low = json.loads(
        (REPO / "tests/fixtures/devflow/descriptor-v2-low-invalid.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(TaskDescriptorError, match="must be xhigh"):
        TaskDescriptor.from_mapping(low)
    legacy = json.loads(
        (REPO / "tests/fixtures/devflow/descriptor-v1-low.json").read_text(
            encoding="utf-8"
        )
    )
    assert legacy["max_recovery_generations"] == 1
    assert TaskDescriptor.from_mapping(legacy).max_recovery_generations == 0
    current = json.loads(
        (REPO / "tests/fixtures/devflow/descriptor-v2-xhigh.json").read_text(
            encoding="utf-8"
        )
    )
    current["max_recovery_generations"] = 1
    with pytest.raises(TaskDescriptorError, match="must equal 0"):
        TaskDescriptor.from_mapping(current)
    assert run_matrix(REPO / "tests/fixtures/devflow")["status"] == "PASS"


def test_trusted_reproduction_loader_rejects_self_report(
    tmp_path: Path,
) -> None:
    path = _evidence(tmp_path)
    assert load_trusted_reproduction(path).generated_by == "trusted_pre_model_job"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["status"] = "PASS"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="must reproduce FAIL"):
        load_trusted_reproduction(path)


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
