from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEVFLOW = REPO / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from validate_workflows import validate_file  # noqa: E402


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


def test_reusable_unit_allows_only_trusted_repository_bot() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    text = action.read_text(encoding="utf-8")
    assert "using: composite" in text
    assert "openai/codex-action@52fe01ec70a42f454c9d2ebd47598f9fd6893d56" in text
    assert "http://127.0.0.1:8787/v1/responses" in text
    assert 'allow-bots: "true"' in text
    assert "allow-bot-users: github-actions[bot]" in text
    assert "allow-users:" not in text
    assert "${{ inputs.api-key }}" in text
    assert "secrets." not in text
    assert validate_file(action) == []


def test_structured_result_uses_action_output_not_absolute_output_file() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    action_text = action.read_text(encoding="utf-8")
    assert "value: ${{ steps.run-codex.outputs.final-message }}" in action_text
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
    assert (
        'git config user.email "41898282+github-actions[bot]@users.noreply.github.com"'
        in merge_section
    )
    assert "Fail closed when automatic merge boundary is blocked" in merge_section
    assert "Notify only when automatic merge is genuinely blocked" not in text
    assert "AUTO_MERGE_BOUNDARY=BLOCKED" in merge_section
    assert validate_file(workflow) == []
