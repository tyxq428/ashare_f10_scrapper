from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEVFLOW = REPO / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from validate_codex_entrypoints import validate  # noqa: E402


def text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def test_repository_wide_codex_trigger_surface_is_zero() -> None:
    result = validate()
    assert result["status"] == "PASS", result["errors"]
    assert result["automatic_model_paths"] == 0
    assert result["automatic_paid_probe_retries"] == 0
    assert result["legacy_rerun_audit_present"] is True


def test_auto_recovery_cannot_watch_model_or_paid_probe_workflows() -> None:
    workflow = text(".github/workflows/devflow-auto-recovery.yml")
    assert "      - Codex Task\n" not in workflow
    assert "      - Devflow Relay Health\n" not in workflow
    assert "actions/workflows/codex-task.yml/dispatches" not in workflow
    assert "steps.decision.outputs.action == 'RETRY_CODEX'" not in workflow
    assert "AUTOMATIC_PAID_RELAY_PROBE_RETRIES=0" in workflow


def test_relay_health_defaults_to_zero_request_and_requires_exact_paid_confirmation() -> None:
    workflow = text(".github/workflows/devflow-relay-health.yml")
    assert "default: configuration_only" in workflow
    assert "I_ACCEPT_ONE_PAID_RESPONSES_PROBE" in workflow
    assert "RESPONSES_REQUESTS_SENT=0" in workflow
    assert workflow.count("python scripts/devflow/relay_health.py") == 1
    assert "This workflow is never automatically retried" in workflow
    assert "RUN_ATTEMPT: ${{ github.run_attempt }}" in workflow
    assert 'test "$RUN_ATTEMPT" = "1"' in workflow
    assert "github.run_attempt == 1" in workflow
    assert "A GitHub UI rerun of paid mode is blocked before the request" in workflow


def test_secret_audit_validates_real_activation_before_environment_binding() -> None:
    workflow = text(".github/workflows/devflow-secret-audit.yml")
    validate_index = workflow.index("  validate-source:")
    audit_index = workflow.index("  audit-public-logs:")
    environment_index = workflow.index("    environment:")
    assert validate_index < audit_index <= environment_index
    assert "AUDIT_CONFIRMED_MODEL_RUN" in workflow
    assert "Codex One-Time Activation" in workflow
    assert "CODEX_MODEL_SESSION_STARTED activation_id=" in workflow
    assert "workflow_run:" not in workflow


def test_manifest_records_legacy_rerun_and_paid_probe_boundaries() -> None:
    manifest = json.loads(text(".devflow/codex-entrypoints.yaml"))
    quarantine = manifest["historical_rerun_quarantine"]
    assert quarantine["branch_pattern"] == "task/codex-*"
    assert quarantine["descriptor_must_be_absent"] is True
    assert quarantine["disabled_action_required"] is True
    assert quarantine["model_reference_forbidden"] is True
    paid = manifest["paid_probe_policy"]
    assert paid["default_mode"] == "configuration_only"
    assert paid["automatic_retry"] is False
    assert paid["github_rerun_paid_request"] is False
    assert paid["paid_request_requires_run_attempt"] == 1
    assert paid["maximum_requests_per_dispatch"] == 1
    audit = manifest["secret_audit_policy"]
    assert audit["automatic_trigger"] is False
    assert audit["environment_bound_after_source_validation"] is True


def test_permanent_legacy_rerun_audit_is_secret_free() -> None:
    workflow = text(".github/workflows/devflow-legacy-codex-rerun-audit.yml")
    assert "legacy_codex_branch_audit.py" in workflow
    assert "task/codex-" in workflow
    assert "agent-runtime" not in workflow
    assert "secrets.AGENT_" not in workflow
    assert "openai/codex-action@" not in workflow
