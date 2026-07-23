from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEVFLOW = REPO / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from recovery_policy import classify  # noqa: E402
from task_descriptor import TaskDescriptor  # noqa: E402
from validate_workflows import validate_file  # noqa: E402


def _failed_job(step_name: str) -> dict[str, object]:
    return {
        "jobs": [
            {
                "name": "gate-and-continue",
                "steps": [
                    {"name": "Set up job", "conclusion": "success"},
                    {"name": step_name, "conclusion": "failure"},
                ],
            }
        ]
    }


def test_codex_entry_job_owns_environment_secret_boundary() -> None:
    workflow = REPO / ".github/workflows/codex-task.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "name: agent-runtime" in text
    assert "deployment: false" in text
    assert "./.github/actions/codex-thin-worker" in text
    assert "uses: ./.github/workflows/_reusable-codex-thin-worker.yml" not in text
    assert "\n  push:\n" not in text
    assert validate_file(workflow) == []


def test_reusable_unit_stops_before_model_when_policy_is_disabled() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    text = action.read_text(encoding="utf-8")
    policy = json.loads((REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8"))
    assert policy["mode"] == "disabled"
    assert "using: composite" in text
    assert "CODEX_POLICY_DISABLED" in text
    assert "CODEX_MODEL_INVOCATION=DISABLED" in text
    assert "openai/codex-action@" not in text
    assert "secrets." not in text
    assert validate_file(action) == []


def test_new_task_template_defaults_xhigh_and_legacy_low_remains_readable() -> None:
    template = json.loads(
        (REPO / "docs/process/templates/codex_task.template.yaml").read_text(encoding="utf-8")
    )
    current = TaskDescriptor.from_mapping(template)
    assert current.reasoning_effort == "xhigh"

    legacy = dict(template)
    legacy["reasoning_effort"] = "low"
    assert TaskDescriptor.from_mapping(legacy).reasoning_effort == "low"


def test_recovery_generator_forces_xhigh_tasks() -> None:
    script = REPO / "scripts/devflow/recovery_task.py"
    text = script.read_text(encoding="utf-8")
    assert 'value["reasoning_effort"] = "xhigh"' in text

    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    assert validate_file(workflow) == []


def test_structured_result_uses_action_output_not_absolute_output_file() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    action_text = action.read_text(encoding="utf-8")
    assert "value: ${{ steps.policy.outputs.final-message }}" in action_text
    assert "output-file:" not in action_text

    workflow = REPO / ".github/workflows/codex-task.yml"
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "CODEX_FINAL_MESSAGE: ${{ steps.codex.outputs.final-message }}" in workflow_text
    assert "Path('/tmp/codex-result.json').write_text" in workflow_text
    assert 'test "${{ steps.result.outcome }}" = "success"' in workflow_text


def test_nonfunctional_reusable_workflow_is_removed() -> None:
    legacy = REPO / ".github/workflows/_reusable-codex-thin-worker.yml"
    assert not legacy.exists()


def test_publish_and_continuation_do_not_receive_agent_runtime() -> None:
    workflow = REPO / ".github/workflows/codex-task.yml"
    text = workflow.read_text(encoding="utf-8")
    publish = text.split("\n  publish:\n", 1)[1]
    assert "agent-runtime" not in publish
    assert "secrets.AGENT_" not in publish


def test_product_gate_scopes_candidate_from_merge_base_and_fails_closed() -> None:
    workflow = REPO / ".github/workflows/devflow-product-gate.yml"
    text = workflow.read_text(encoding="utf-8")
    initial_scope = text.split("\n      - name: Run full product gate", 1)[0]
    assert 'git merge-base --is-ancestor "$EXPECTED_BASE_SHA" HEAD' in initial_scope
    assert 'MERGE_BASE="$(git merge-base origin/main HEAD)"' in initial_scope
    assert '--base "$MERGE_BASE"' in initial_scope
    assert "--base origin/main" not in initial_scope
    assert "product-scope-result.json" in initial_scope
    assert "Fail closed on changed-path scope violation" in text
    assert "steps.scope.outcome != 'success'" in text
    assert validate_file(workflow) == []


def test_product_gate_configures_bot_identity_and_centralizes_merge_failure() -> None:
    workflow = REPO / ".github/workflows/devflow-product-gate.yml"
    text = workflow.read_text(encoding="utf-8")
    merge_section = text.split(
        "\n      - name: Reconcile latest main, re-run gate if needed, and merge low-risk candidate\n",
        1,
    )[1]
    assert 'git config user.name "github-actions[bot]"' in merge_section
    assert 'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"' in merge_section
    assert "Fail closed when automatic merge boundary is blocked" in merge_section
    assert "Notify only when automatic merge is genuinely blocked" not in text
    assert "AUTO_MERGE_BOUNDARY=BLOCKED" in merge_section
    assert validate_file(workflow) == []


def test_product_gate_merge_boundary_is_a_real_human_gate() -> None:
    decision = classify(
        source_workflow="Devflow Product Gate",
        source_run_id=999,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=_failed_job("Fail closed when automatic merge boundary is blocked"),
    )
    assert decision.action == "HUMAN_REQUIRED"
    assert decision.reason_code == "AUTO_MERGE_BLOCKED"
    assert decision.notification_type == "HUMAN_REQUIRED"


def test_product_gate_scope_failure_precedes_code_repair() -> None:
    decision = classify(
        source_workflow="Devflow Product Gate",
        source_run_id=1000,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=_failed_job("Fail closed on changed-path scope violation"),
    )
    assert decision.action == "SECURITY_BLOCKED"
    assert decision.reason_code == "SECURITY_CONTROL_FAILED"


def test_auto_recovery_does_not_synthesize_state_consistency_codex_scope() -> None:
    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "Repair the deterministic devflow state or validation failure" not in text
    assert 'SOURCE_NAME" == "Devflow State Consistency"' not in text
    assert validate_file(workflow) == []
