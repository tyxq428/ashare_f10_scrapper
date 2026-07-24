from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "scripts/devflow"
sys.path.insert(0, str(DEVFLOW))

from assert_auto_recovery_boundaries import validate as validate_auto_recovery  # noqa: E402
from validate_notification_channels import validate as validate_channels  # noqa: E402

INCIDENT = ROOT / ".github/workflows/devflow-incident.yml"
AUTO_RECOVERY = ROOT / ".github/workflows/devflow-auto-recovery.yml"
PRODUCT_GATE = ROOT / ".github/workflows/devflow-product-gate.yml"
POST_MERGE = ROOT / ".github/workflows/devflow-post-merge.yml"
TERMINAL_STATE = ROOT / ".github/workflows/devflow-terminal-state-notify.yml"


def test_incident_uses_task_level_dispatch_not_raw_workflow_completion() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    assert "repository_dispatch:" in text
    assert "devflow_notify" in text
    assert "workflow_run:" not in text
    assert "notification_event.py prepare" in text
    assert "devflow-task-control-chatgpt-web-codex-devflow-v1" not in text


def test_bark_transport_is_single_attempt_fail_open_and_secret_isolated() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    assert "name: notification-runtime" in text
    assert "BARK_PUSH_URL: ${{ secrets.BARK_PUSH_URL }}" in text
    assert "github.run_attempt == 1" in text
    assert "continue-on-error: true" in text
    assert text.count("--request POST") == 1
    assert "--retry 0" in text
    assert "--output /dev/null" in text
    assert "BARK_DELIVERY=FAILED_FAIL_OPEN" in text
    assert "BARK_AUTOMATIC_RETRIES=0" in text
    assert "BARK_REQUESTS_PER_LOGICAL_NOTIFICATION_MAX=1" in text
    assert "agent-runtime" not in text
    assert "secrets.AGENT_" not in text
    assert "openai/codex-action@" not in text


def test_auto_recovery_binds_terminal_events_without_retrying_bark() -> None:
    text = AUTO_RECOVERY.read_text(encoding="utf-8")
    assert "notification_event.py resolve-task" in text
    assert "value['task_id'] = resolved['task_id']" in text
    assert "assert_auto_recovery_boundaries.py" in text
    assert "      - Devflow Incident\n" not in text
    assert "      - Devflow Terminal State Notification\n" not in text
    assert "notification-runtime" not in text
    assert "BARK_PUSH_URL" not in text
    assert validate_auto_recovery(AUTO_RECOVERY) == []


def test_terminal_completion_producer_is_main_state_only_and_secret_free() -> None:
    text = TERMINAL_STATE.read_text(encoding="utf-8")
    assert "push:" in text
    assert "      - main" in text
    assert "docs/implementation/*/task_state.yaml" in text
    assert "terminal_notification_scan.py" in text
    assert "devflow_notify" in text
    assert "workflow_run:" not in text
    assert "notification-runtime" not in text
    assert "BARK_PUSH_URL" not in text
    assert "--request POST" not in text
    assert "BARK_REQUESTS_IN_THIS_WORKFLOW=0" in text


def test_failed_product_and_post_merge_paths_do_not_dispatch_duplicates() -> None:
    product = PRODUCT_GATE.read_text(encoding="utf-8")
    failure_prefix = product.split(
        "Notify when a task is not approved for automatic merge",
        1,
    )[0]
    assert "'event_type': 'devflow_notify'" not in failure_prefix
    assert "Centralized Auto Recovery will classify the terminal task event" in product
    assert "notification_event.py resolve-task" in product
    assert "'task_id': resolved['task_id']" in product

    post_merge = POST_MERGE.read_text(encoding="utf-8")
    assert "'event_type': 'devflow_notify'" not in post_merge
    assert "Centralized Auto Recovery will classify the terminal task event" in post_merge


def test_notification_channel_manifest_matches_workflow_surface() -> None:
    summary = validate_channels()
    assert summary["status"] == "PASS", summary["errors"]
    assert summary["bark_post_locations"] == 1
    assert summary["automatic_bark_retries"] == 0
