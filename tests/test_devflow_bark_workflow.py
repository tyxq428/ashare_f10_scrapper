# ruff: noqa: E402, I001
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEVFLOW = ROOT / "scripts/devflow"
sys.path.insert(0, str(DEVFLOW))

from assert_auto_recovery_boundaries import validate as validate_auto_recovery
from validate_notification_channels import validate as validate_channels

INCIDENT = ROOT / ".github/workflows/devflow-incident.yml"
AUTO_RECOVERY = ROOT / ".github/workflows/devflow-auto-recovery.yml"
PRODUCT_GATE = ROOT / ".github/workflows/devflow-product-gate.yml"
POST_MERGE = ROOT / ".github/workflows/devflow-post-merge.yml"
STATE_CONSISTENCY = ROOT / ".github/workflows/devflow-state-consistency.yml"
OBSOLETE_TERMINAL = ROOT / ".github/workflows/devflow-terminal-state-notify.yml"
RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"


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
    assert "--proto '=https'" in text
    assert "--tlsv1.2" in text
    assert "--show-error" not in text
    assert "--output /dev/null" in text
    assert "BARK_DELIVERY=FAILED_FAIL_OPEN" in text
    assert "BARK_AUTOMATIC_RETRIES=0" in text
    assert "BARK_REQUESTS_PER_LOGICAL_NOTIFICATION_MAX=1" in text
    assert "BARK_RESPONSE_BODY_STORED=0" in text
    assert "BARK_RESPONSE_HEADERS_STORED=0" in text
    assert "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0" in text
    assert "BARK_SECRET_VALUE_STORED=0" in text
    assert "agent-runtime" not in text
    assert "secrets.AGENT_" not in text
    assert "openai/codex-action@" not in text


def test_bark_receipt_artifact_and_issue_index_are_bounded_and_fail_open() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    comment_script = RECEIPT_COMMENT.read_text(encoding="utf-8")
    assert "bark_delivery_result.py build" in text
    assert "bark_delivery_result.py validate" in text
    assert "bark_delivery_receipt_comment.py" in text
    assert text.count("actions/upload-artifact@") == 1
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "path: /tmp/bark-delivery-result.json" in text
    assert "bark-delivery-receipt-${{" in text
    assert "if-no-files-found: error" in text
    assert "retention-days: 14" in text
    assert "compression-level: 0" in text
    assert "BARK_RECEIPT_ARTIFACT=UPLOADED" in text
    assert "BARK_RECEIPT_ARTIFACT=FAILED_FAIL_OPEN" in text
    assert "BARK_RECEIPT_ISSUE_INDEX=RECORDED_OR_DEDUPLICATED" in text
    assert "BARK_RECEIPT_ISSUE_INDEX=FAILED_FAIL_OPEN" in text
    assert "devflow-bark-delivery-receipt:" in comment_script
    assert "issues: write" in text


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


def test_completion_dispatch_waits_for_state_consistency_and_fails_open() -> None:
    text = STATE_CONSISTENCY.read_text(encoding="utf-8")
    assert "notify-terminal-state:" in text
    assert "needs: consistency" in text
    assert "github.event_name == 'push' && github.ref_name == 'main'" in text
    assert "continue-on-error: true" in text
    assert "contents: write" in text
    assert "ref: ${{ github.sha }}" in text
    assert "fetch-depth: 0" in text
    assert "terminal_notification_scan.py" in text
    assert "devflow_notify" in text
    assert "TERMINAL_NOTIFICATION_FAILURE=FAIL_OPEN" in text
    assert "STATE_CONSISTENCY_REQUIRED_BEFORE_COMPLETION=YES" in text
    assert "NOTIFICATION_FAILURE_AUTO_RECOVERY=0" in text
    assert "notification-runtime" not in text
    assert "BARK_PUSH_URL" not in text
    assert "--request POST" not in text
    assert "BARK_REQUESTS_IN_THIS_WORKFLOW=0" in text
    assert not OBSOLETE_TERMINAL.exists()


def test_failed_product_and_post_merge_paths_do_not_dispatch_duplicates() -> None:
    product = PRODUCT_GATE.read_text(encoding="utf-8")
    failure_prefix = product.split(
        "Notify when a task is not approved for automatic merge",
        1,
    )[0]
    assert "'event_type': 'devflow_notify'" not in failure_prefix
    assert (
        "Centralized Auto Recovery will classify the terminal task event"
        in product
    )
    assert "notification_event.py resolve-task" in product
    assert "'task_id': resolved['task_id']" in product

    post_merge = POST_MERGE.read_text(encoding="utf-8")
    assert "'event_type': 'devflow_notify'" not in post_merge
    assert (
        "Centralized Auto Recovery will classify the terminal task event"
        in post_merge
    )


def test_notification_channel_manifest_matches_workflow_surface() -> None:
    summary = validate_channels()
    assert summary["status"] == "PASS", summary["errors"]
    assert summary["completion_producer"].endswith(
        "devflow-state-consistency.yml"
    )
    assert summary["completion_delivery_fail_open"] is True
    assert summary["bark_post_locations"] == 1
    assert summary["automatic_bark_retries"] == 0
