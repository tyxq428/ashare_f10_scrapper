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
TERMINAL_PRODUCER = ROOT / ".github/workflows/devflow-terminal-state-notify.yml"
LIVE_RETEST = ROOT / ".github/workflows/bark-all-status-live-retest-v2.yml"
RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"


def test_incident_uses_task_level_dispatch_not_raw_workflow_completion() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    assert "repository_dispatch:" in text
    assert "devflow_notify" in text
    assert "workflow_run:" not in text
    assert "notification_event.py prepare" in text
    assert "devflow-task-control-chatgpt-web-codex-devflow-v1" not in text


def test_completed_incident_deduplicates_across_notification_generations() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    assert 'COMPLETION_MARKER="devflow-task-completed:${TASK_ID}"' in text
    assert "devflow-task-completed:{value['task_id']}" in text
    assert "TASK_COMPLETION=ALREADY_RECORDED" in text
    assert "grep -Fq -- \"$MARKER\"" in text
    assert "grep -Fq -- \"$COMPLETION_MARKER\"" in text
    assert "devflow-task-control-${{" in text


def test_bark_transport_is_single_attempt_fail_open_and_secret_isolated() -> None:
    text = INCIDENT.read_text(encoding="utf-8")
    assert "name: notification-runtime" in text
    assert "BARK_PUSH_URL: ${{ secrets.BARK_PUSH_URL }}" in text
    assert "github.run_attempt == 1" in text
    assert "continue-on-error: true" in text
    assert text.count("--request POST") == 1
    assert "--retry 0" in text
    assert "--proto '=http,https'" in text
    assert "CURL_PROTOCOL_ARGS+=(--tlsv1.2)" in text
    assert 'BARK_ENDPOINT="${BARK_ENDPOINT%/}"' in text
    assert "SKIPPED_INVALID_CONFIGURATION" in text
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




def test_owner_approved_http_or_https_all_status_retest_is_bounded() -> None:
    text = LIVE_RETEST.read_text(encoding="utf-8")
    assert "bark-all-status-live-retest-v3-http-reservation:20260724" in text
    assert "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]" in text
    assert "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)" in text
    assert "github.run_attempt == 1" in text
    assert "--proto '=http,https'" in text
    assert "VALID_HTTP" in text
    assert "VALID_HTTPS" in text
    assert "CURL_PROTOCOL_ARGS+=(--tlsv1.2)" in text
    assert "--retry 0" in text
    assert text.count("--request POST") == 1
    assert "EXPECTED_REAL_BARK_REQUESTS=4" in text
    assert "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED" in text
    assert "--show-error" not in text
    assert "agent-runtime" not in text
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


def test_state_consistency_validates_only_and_has_no_notification_transport() -> None:
    text = STATE_CONSISTENCY.read_text(encoding="utf-8")
    assert "validate_state.py" in text
    assert "validate_workflows.py" in text
    assert "pytest -q" in text
    assert "notify-terminal-state:" not in text
    assert "terminal_notification_scan.py" not in text
    assert "devflow_notify" not in text
    assert "contents: write" not in text
    assert "BARK_PUSH_URL" not in text
    assert "--request POST" not in text


def test_completion_producer_runs_only_after_successful_main_push_validation() -> None:
    text = TERMINAL_PRODUCER.read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert "      - Devflow State Consistency" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "ref: ${{ github.event.workflow_run.head_sha }}" in text
    assert "fetch-depth: 2" in text
    assert "git merge-base --is-ancestor" in text
    assert 'git rev-parse "${SOURCE_HEAD_SHA}^1"' in text
    assert "terminal_notification_scan.py" in text
    assert "devflow_notify" in text
    assert "TERMINAL_NOTIFICATION_FAILURE=FAIL_OPEN" in text
    assert "STATE_CONSISTENCY_SUCCESS_REQUIRED=YES" in text
    assert "RAW_WORKFLOW_FAILURE_NOTIFICATIONS=0" in text
    assert "BARK_REQUESTS_IN_THIS_WORKFLOW=0" in text
    assert "NOTIFICATION_FAILURE_AUTO_RECOVERY=0" in text
    assert "notification-runtime" not in text
    assert "BARK_PUSH_URL" not in text
    assert "--request POST" not in text


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
        "devflow-terminal-state-notify.yml"
    )
    assert summary["completion_scanner_workflows"] == [
        ".github/workflows/devflow-terminal-state-notify.yml"
    ]
    assert summary["stable_completion_marker"] == (
        "devflow-task-completed:<task-id>"
    )
    assert summary["completion_delivery_fail_open"] is True
    assert summary["bark_post_locations"] == 1
    assert summary["automatic_bark_retries"] == 0
    assert summary["allowed_bark_schemes"] == ["http", "https"]
    assert summary["one_time_live_retest"]["expected_requests"] == 4
    assert summary["bark_receipt_workflows"] == [
        ".github/workflows/devflow-incident.yml"
    ]
    assert summary["bark_receipt_artifact_uploads"] == 1
    assert summary["bark_receipt_retention_days"] == 14
    assert summary["bark_receipt_issue_index"] is True
