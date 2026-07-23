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


def test_reusable_unit_is_composite_action_with_pinned_codex_action() -> None:
    action = REPO / ".github/actions/codex-thin-worker/action.yml"
    text = action.read_text(encoding="utf-8")
    assert "using: composite" in text
    assert "openai/codex-action@52fe01ec70a42f454c9d2ebd47598f9fd6893d56" in text
    assert "http://127.0.0.1:8787/v1/responses" in text
    assert "${{ inputs.api-key }}" in text
    assert "secrets." not in text
    assert validate_file(action) == []


def test_nonfunctional_reusable_workflow_is_removed() -> None:
    legacy = REPO / ".github/workflows/_reusable-codex-thin-worker.yml"
    assert not legacy.exists()


def test_publish_and_continuation_do_not_receive_agent_runtime() -> None:
    workflow = REPO / ".github/workflows/codex-task.yml"
    text = workflow.read_text(encoding="utf-8")
    publish = text.split("\n  publish:\n", 1)[1]
    assert "agent-runtime" not in publish
    assert "secrets.AGENT_" not in publish
