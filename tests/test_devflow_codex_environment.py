from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEVFLOW = REPO / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from recovery_policy import classify  # noqa: E402
from task_descriptor import TaskDescriptor  # noqa: E402
from validate_codex_entrypoints import validate as validate_entrypoints  # noqa: E402
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


def test_codex_entry_is_manual_trusted_control_and_model_free() -> None:
    workflow = REPO / ".github/workflows/codex-task.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "github.actor == 'tyxq428'" in text
    assert "path: control" in text
    assert "path: workspace" in text
    assert "codex_candidate_review.py" in text
    assert "CODEX_MODEL_INVOCATION=DISABLED" in text
    assert "Task branches are data-only" in text
    assert "agent-runtime" not in text
    assert "secrets." not in text
    assert "openai/codex-action@" not in text
    assert "github-actions[bot]" not in text
    assert "\n  push:\n" not in text
    assert validate_file(workflow) == []


def test_reusable_unit_stops_before_model_when_policy_is_disabled() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    text = action.read_text(encoding="utf-8")
    policy = json.loads(
        (REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8")
    )
    assert policy["mode"] == "disabled"
    assert "using: composite" in text
    assert "CODEX_POLICY_DISABLED" in text
    assert "CODEX_MODEL_INVOCATION=DISABLED" in text
    assert "openai/codex-action@" not in text
    assert "secrets." not in text
    assert validate_file(action) == []


def test_new_task_template_is_xhigh_zero_recovery_and_web_assessed() -> None:
    template = json.loads(
        (REPO / "docs/process/templates/codex_task.template.yaml").read_text(
            encoding="utf-8"
        )
    )
    current = TaskDescriptor.from_mapping(template)
    assert current.reasoning_effort == "xhigh"
    assert current.max_recovery_generations == 0
    assert template["web_resolution_assessment"]["attempted"] is True
    assert template["failure_context"]["reason_code"].startswith("LOCAL_")

    legacy = dict(template)
    legacy["schema_version"] = 1
    legacy["reasoning_effort"] = "low"
    legacy["max_recovery_generations"] = 1
    parsed = TaskDescriptor.from_mapping(legacy)
    assert parsed.reasoning_effort == "low"
    assert parsed.max_recovery_generations == 0


def test_production_recovery_task_generator_is_removed() -> None:
    assert not (REPO / "scripts/devflow/recovery_task.py").exists()
    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "actions/workflows/codex-task.yml/dispatches" not in workflow_text
    assert "steps.decision.outputs.action == 'RETRY_CODEX'" not in workflow_text
    assert "python scripts/devflow/recovery_task.py" not in workflow_text
    assert "      - Codex Task\n" not in workflow_text
    assert validate_file(workflow) == []


def test_hard_disabled_entry_has_no_model_or_publish_pipeline() -> None:
    workflow = REPO / ".github/workflows/codex-task.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "CODEX_FINAL_MESSAGE" not in text
    assert "/tmp/codex-result.json" not in text
    assert "secret-bearing-read-only-codex" not in text
    assert "secret-free-publish" not in text
    assert "devflow_product_gate" not in text
    assert "openai/codex-action@" not in text


def test_product_gate_scopes_candidate_and_never_dispatches_codex() -> None:
    workflow = REPO / ".github/workflows/devflow-product-gate.yml"
    text = workflow.read_text(encoding="utf-8")
    initial_scope = text.split("\n      - name: Run full product gate", 1)[0]
    assert 'git merge-base --is-ancestor "$EXPECTED_BASE_SHA" HEAD' in initial_scope
    assert 'MERGE_BASE="$(git merge-base origin/main HEAD)"' in initial_scope
    assert '--base "$MERGE_BASE"' in initial_scope
    assert "--base origin/main" not in initial_scope
    assert "product-scope-result.json" in initial_scope
    assert "Fail closed on changed-path scope violation" in text
    assert "PRODUCT_GATE_WEB_REPAIR_REQUIRED" in text
    assert "actions/workflows/codex-task.yml/dispatches" not in text
    assert "python scripts/devflow/recovery_task.py" not in text
    assert "RECOVERY_GENERATION" not in text
    assert validate_file(workflow) == []


def test_product_gate_configures_bot_identity_and_centralizes_merge_failure() -> None:
    workflow = REPO / ".github/workflows/devflow-product-gate.yml"
    text = workflow.read_text(encoding="utf-8")
    merge_section = text.split(
        "\n      - name: Reconcile latest main, re-run gate if needed, and merge low-risk candidate\n",
        1,
    )[1]
    assert 'git config user.name "github-actions[bot]"' in merge_section
    assert (
        '"41898282+github-actions[bot]@users.noreply.github.com"'
        in merge_section
    )
    assert "Fail closed when automatic merge boundary is blocked" in merge_section
    assert "AUTO_MERGE_BOUNDARY=BLOCKED" in merge_section
    assert validate_file(workflow) == []


def test_product_gate_merge_boundary_is_a_real_human_gate() -> None:
    decision = classify(
        source_workflow="Devflow Product Gate",
        source_run_id=999,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=_failed_job(
            "Fail closed when automatic merge boundary is blocked"
        ),
    )
    assert decision.action == "HUMAN_REQUIRED"
    assert decision.reason_code == "AUTO_MERGE_BLOCKED"
    assert decision.notification_type == "HUMAN_REQUIRED"


def test_product_gate_scope_failure_precedes_web_repair() -> None:
    decision = classify(
        source_workflow="Devflow Product Gate",
        source_run_id=1000,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=_failed_job("Fail closed on changed-path scope violation"),
    )
    assert decision.action == "SECURITY_BLOCKED"
    assert decision.reason_code == "SECURITY_CONTROL_FAILED"


def test_all_runtime_entrypoints_pass_zero_model_manifest() -> None:
    summary = validate_entrypoints()
    assert summary["status"] == "PASS", summary["errors"]
    assert summary["automatic_model_paths"] == 0
