from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST = Path(".devflow/notification-channels.yaml")
WORKFLOW_ROOT = Path(".github/workflows")
INCIDENT = WORKFLOW_ROOT / "devflow-incident.yml"
STATE_CONSISTENCY = WORKFLOW_ROOT / "devflow-state-consistency.yml"
TERMINAL_PRODUCER = WORKFLOW_ROOT / "devflow-terminal-state-notify.yml"
AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"
LIVE_RETEST = WORKFLOW_ROOT / "bark-all-status-live-retest-v2.yml"
RECEIPT_BUILDER = Path("scripts/devflow/bark_delivery_result.py")
RECEIPT_COMMENT = Path("scripts/devflow/bark_delivery_receipt_comment.py")
UPLOAD_ARTIFACT_REF = (
    "actions/upload-artifact@"
    "ea165f8d65b6e75b540449e92b4886f43607fa02"
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load notification manifest: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("notification manifest root must be an object")
    return value


def validate() -> dict[str, Any]:
    errors: list[str] = []
    try:
        manifest = _load_object(MANIFEST)
    except ValueError as exc:
        return {"status": "FAIL", "errors": [str(exc)]}

    expected_types = [
        "COMPLETED",
        "INTERRUPTED",
        "HUMAN_REQUIRED",
        "SECURITY_BLOCKED",
    ]
    if manifest.get("schema_version") != 1:
        errors.append("notification manifest schema_version must be 1")
    if manifest.get("valuable_notification_types") != expected_types:
        errors.append("valuable notification types must match terminal policy")

    event_bus = manifest.get("event_bus")
    if not isinstance(event_bus, dict):
        errors.append("notification event_bus must be an object")
    else:
        if event_bus.get("event_type") != "devflow_notify":
            errors.append("notification event type must be devflow_notify")
        if event_bus.get("workflow") != INCIDENT.as_posix():
            errors.append("notification event bus must terminate in Devflow Incident")
        if event_bus.get("raw_workflow_run_notifications") is not False:
            errors.append("raw workflow_run notifications must remain disabled")

    channels = manifest.get("channels")
    canonical_issue: dict[str, Any] = {}
    bark: dict[str, Any] = {}
    if not isinstance(channels, dict):
        errors.append("notification channels must be an object")
    else:
        issue_value = channels.get("canonical_issue")
        if not isinstance(issue_value, dict):
            errors.append("canonical Issue channel policy is missing")
        else:
            canonical_issue = issue_value
        bark_value = channels.get("bark")
        if not isinstance(bark_value, dict):
            errors.append("Bark channel policy is missing")
        else:
            bark = bark_value

    expected_issue = {
        "enabled": True,
        "deduplication_marker": "task_id+fingerprint+notification_type",
        "stable_completion_marker": "devflow-task-completed:<task-id>",
    }
    for key, expected in expected_issue.items():
        if canonical_issue.get(key) != expected:
            errors.append(f"canonical Issue policy mismatch for {key}")

    expected_bark = {
        "enabled": True,
        "environment": "notification-runtime",
        "secret_name": "BARK_PUSH_URL",
        "automatic_retry": False,
        "github_rerun_resend": False,
        "run_attempt_must_equal": 1,
        "maximum_requests_per_notification": 1,
        "failure_changes_task_state": False,
        "allowed_schemes": ["http", "https"],
        "https_minimum_tls": "1.2",
        "http_transport_is_unencrypted": True,
    }
    for key, expected in expected_bark.items():
        if bark.get(key) != expected:
            errors.append(f"Bark policy mismatch for {key}")

    receipt: dict[str, Any] = {}
    receipt_value = bark.get("receipt")
    if not isinstance(receipt_value, dict):
        errors.append("Bark delivery receipt policy is missing")
    else:
        receipt = receipt_value
    expected_receipt = {
        "enabled": True,
        "builder": RECEIPT_BUILDER.as_posix(),
        "issue_comment_renderer": RECEIPT_COMMENT.as_posix(),
        "artifact_name_prefix": "bark-delivery-receipt-",
        "artifact_file": "/tmp/bark-delivery-result.json",
        "retention_days": 14,
        "maximum_files": 1,
        "issue_index_enabled": True,
        "artifact_upload_fail_open": True,
        "issue_index_fail_open": True,
        "response_body_stored": False,
        "response_headers_stored": False,
        "endpoint_stored": False,
        "raw_error_stored": False,
        "secret_value_stored": False,
    }
    for key, expected in expected_receipt.items():
        if receipt.get(key) != expected:
            errors.append(f"Bark receipt policy mismatch for {key}")

    producer = manifest.get("completion_producer")
    if not isinstance(producer, dict):
        errors.append("completion producer policy is missing")
    else:
        expected_producer = {
            "workflow": TERMINAL_PRODUCER.as_posix(),
            "trigger": "workflow_run_success",
            "source_workflow": "Devflow State Consistency",
            "source_event": "push",
            "source_branch": "main",
            "source_head_checkout": True,
            "first_parent_diff": True,
            "single_producer": True,
            "strict_done_required": True,
            "state_consistency_pass_required": True,
            "failure_changes_task_state": False,
        }
        for key, expected in expected_producer.items():
            if producer.get(key) != expected:
                errors.append(f"completion producer policy mismatch for {key}")


    live_retest = manifest.get("one_time_live_retest")
    expected_live_retest = {
        "test_id": "bark-all-status-live-retest-v3-http-20260724",
        "workflow": LIVE_RETEST.as_posix(),
        "issue_number": 61,
        "reservation_marker": (
            "bark-all-status-live-retest-v3-http-reservation:20260724"
        ),
        "result_marker": "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
        "statuses": expected_types,
        "expected_requests": 4,
        "allowed_schemes": ["http", "https"],
        "run_attempt_must_equal": 1,
        "automatic_retry": False,
        "response_body_stored": False,
        "response_headers_stored": False,
        "endpoint_stored": False,
        "raw_error_stored": False,
        "secret_value_stored": False,
    }
    if live_retest != expected_live_retest:
        errors.append("one-time Bark HTTP/HTTPS live-retest policy mismatch")

    workflow_text: dict[Path, str] = {}
    for path in sorted(WORKFLOW_ROOT.glob("*.yml")):
        workflow_text[path] = path.read_text(encoding="utf-8")

    environment_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if "notification-runtime" in text
    ]
    expected_environment_users = [
        LIVE_RETEST.as_posix(),
        INCIDENT.as_posix(),
    ]
    if environment_users != expected_environment_users:
        errors.append(
            "notification-runtime may be referenced only by Incident and the "
            "owner-approved HTTP/HTTPS live retest: "
            f"{environment_users}"
        )

    secret_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if "${{ secrets.BARK_PUSH_URL }}" in text
    ]
    expected_secret_users = [
        LIVE_RETEST.as_posix(),
        INCIDENT.as_posix(),
    ]
    if secret_users != expected_secret_users:
        errors.append(
            "BARK_PUSH_URL may be referenced only by Incident and the "
            "owner-approved HTTP/HTTPS live retest: "
            f"{secret_users}"
        )

    receipt_script_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if RECEIPT_BUILDER.name in text or RECEIPT_COMMENT.name in text
    ]
    if receipt_script_users != [INCIDENT.as_posix()]:
        errors.append(
            "Bark receipt scripts must be used only by Devflow Incident: "
            f"{receipt_script_users}"
        )

    scanner_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if "terminal_notification_scan.py" in text
    ]
    if scanner_users != [TERMINAL_PRODUCER.as_posix()]:
        errors.append(
            "terminal completion scanner must have one independent producer: "
            f"{scanner_users}"
        )

    for path in (INCIDENT, STATE_CONSISTENCY, TERMINAL_PRODUCER, LIVE_RETEST):
        if not path.is_file():
            errors.append(f"missing notification workflow: {path}")
    for script in (RECEIPT_BUILDER, RECEIPT_COMMENT):
        if not script.is_file():
            errors.append(f"missing Bark receipt script: {script}")

    incident_text = workflow_text.get(INCIDENT, "")
    required_incident = (
        "repository_dispatch:",
        "devflow_notify",
        "notification_event.py prepare",
        "github.run_attempt == 1",
        "continue-on-error: true",
        "devflow-task-completed:${TASK_ID}",
        "devflow-task-completed:{value['task_id']}",
        "TASK_COMPLETION=ALREADY_RECORDED",
        "--retry 0",
        "--proto '=http,https'",
        'BARK_ENDPOINT="${BARK_ENDPOINT%/}"',
        'BARK_ENDPOINT" != http://*',
        'BARK_ENDPOINT" != https://*',
        "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
        "SKIPPED_INVALID_CONFIGURATION",
        "--output /dev/null",
        "bark_delivery_result.py build",
        "bark_delivery_result.py validate",
        "bark_delivery_receipt_comment.py",
        UPLOAD_ARTIFACT_REF,
        "bark-delivery-receipt-${{",
        "path: /tmp/bark-delivery-result.json",
        "if-no-files-found: error",
        "retention-days: 14",
        "compression-level: 0",
        "BARK_DELIVERY=FAILED_FAIL_OPEN",
        "BARK_DELIVERY_RECEIPT=FAILED_FAIL_OPEN",
        "BARK_RECEIPT_ARTIFACT=UPLOADED",
        "BARK_RECEIPT_ARTIFACT=FAILED_FAIL_OPEN",
        "BARK_RECEIPT_ISSUE_INDEX=RECORDED_OR_DEDUPLICATED",
        "BARK_RECEIPT_ISSUE_INDEX=FAILED_FAIL_OPEN",
        "BARK_AUTOMATIC_RETRIES=0",
        "BARK_REQUESTS_PER_LOGICAL_NOTIFICATION_MAX=1",
        "BARK_RESPONSE_BODY_STORED=0",
        "BARK_RESPONSE_HEADERS_STORED=0",
        "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0",
        "BARK_SECRET_VALUE_STORED=0",
    )
    for fragment in required_incident:
        if fragment not in incident_text:
            errors.append(f"Devflow Incident missing Bark guard: {fragment}")
    if incident_text.count("--request POST") != 1:
        errors.append("Devflow Incident must contain exactly one Bark POST location")
    if incident_text.count("actions/upload-artifact@") != 1:
        errors.append(
            "Devflow Incident must contain exactly one receipt Artifact upload"
        )
    if incident_text.count("path: /tmp/bark-delivery-result.json") != 1:
        errors.append("Bark receipt Artifact must contain exactly one JSON path")
    if incident_text.count("bark_delivery_result.py build") != 1:
        errors.append("Devflow Incident must build exactly one Bark receipt")
    if incident_text.count("bark_delivery_result.py validate") != 1:
        errors.append("Devflow Incident must validate exactly one Bark receipt")
    if incident_text.count("bark_delivery_receipt_comment.py") != 1:
        errors.append("Devflow Incident must render exactly one receipt index")
    for forbidden in (
        "workflow_run:",
        "--show-error",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "private_responses_forwarder.py",
        "relay_health.py",
    ):
        if forbidden in incident_text:
            errors.append(f"Devflow Incident contains forbidden path: {forbidden}")


    live_retest_text = workflow_text.get(LIVE_RETEST, "")
    required_live_retest = (
        "issues:",
        "      - assigned",
        "github.event.issue.number == 61",
        "github.event.assignee.login == 'tyxq428'",
        "github.run_attempt == 1",
        "name: notification-runtime",
        "${{ secrets.BARK_PUSH_URL }}",
        "bark-all-status-live-retest-v3-http-reservation:20260724",
        "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
        "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)",
        "render_bark_message",
        "BARK_TITLE_MISSING_STATUS",
        "--retry 0",
        "--proto '=http,https'",
        "VALID_HTTP",
        "VALID_HTTPS",
        "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
        "--output /dev/null",
        "EXPECTED_REAL_BARK_REQUESTS=4",
        "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED",
        "gh issue comment 61",
        UPLOAD_ARTIFACT_REF,
        "bark-all-status-live-retest-v3-${{ github.run_id }}",
        "retention-days: 14",
        "compression-level: 0",
    )
    for fragment in required_live_retest:
        if fragment not in live_retest_text:
            errors.append(f"Bark HTTP/HTTPS live retest missing guard: {fragment}")
    if live_retest_text.count("--request POST") != 1:
        errors.append("Bark HTTP/HTTPS live retest must contain exactly one POST loop")
    if live_retest_text.count("actions/upload-artifact@") != 1:
        errors.append("Bark HTTP/HTTPS live retest must upload exactly one result Artifact")
    for forbidden in (
        "repository_dispatch:",
        "workflow_run:",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "private_responses_forwarder.py",
        "relay_health.py",
        "--show-error",
        "--proto '=https'",
    ):
        if forbidden in live_retest_text:
            errors.append(
                f"Bark HTTP/HTTPS live retest contains forbidden path: {forbidden}"
            )

    comment_text = (
        RECEIPT_COMMENT.read_text(encoding="utf-8")
        if RECEIPT_COMMENT.is_file()
        else ""
    )
    for fragment in (
        "[BARK][DELIVERY_RECEIPT]",
        "devflow-bark-delivery-receipt:",
        "response body, response headers, endpoint diagnostics",
        "artifact_url must identify the exact current-repository Artifact",
    ):
        if fragment not in comment_text:
            errors.append(f"Bark receipt comment renderer missing guard: {fragment}")

    consistency_text = workflow_text.get(STATE_CONSISTENCY, "")
    for fragment in (
        "validate_state.py",
        "validate_workflows.py",
        "validate_codex_entrypoints.py",
        "pytest -q",
        "tests/test_devflow",
    ):
        if fragment not in consistency_text:
            errors.append(f"State Consistency missing validation guard: {fragment}")
    for forbidden in (
        "notify-terminal-state:",
        "terminal_notification_scan.py",
        "devflow_notify",
        "contents: write",
        "notification-runtime",
        "BARK_PUSH_URL",
        "--request POST",
        RECEIPT_BUILDER.name,
        RECEIPT_COMMENT.name,
    ):
        if forbidden in consistency_text:
            errors.append(
                "State Consistency must not produce terminal notifications: "
                f"{forbidden}"
            )

    producer_text = workflow_text.get(TERMINAL_PRODUCER, "")
    required_producer = (
        "workflow_run:",
        "      - Devflow State Consistency",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'main'",
        "ref: ${{ github.event.workflow_run.head_sha }}",
        "fetch-depth: 2",
        "persist-credentials: false",
        "git merge-base --is-ancestor",
        'git rev-parse "${SOURCE_HEAD_SHA}^1"',
        "terminal_notification_scan.py",
        "--source-run-id \"${{ steps.source.outputs.source_run_id }}\"",
        "devflow_notify",
        "TERMINAL_NOTIFICATION_FAILURE=FAIL_OPEN",
        "STATE_CONSISTENCY_SUCCESS_REQUIRED=YES",
        "SOURCE_EVENT_REQUIRED=PUSH",
        "SOURCE_BRANCH_REQUIRED=MAIN",
        "RAW_WORKFLOW_FAILURE_NOTIFICATIONS=0",
        "BARK_REQUESTS_IN_THIS_WORKFLOW=0",
        "NOTIFICATION_FAILURE_AUTO_RECOVERY=0",
    )
    for fragment in required_producer:
        if fragment not in producer_text:
            errors.append(f"terminal completion producer missing guard: {fragment}")
    for forbidden in (
        "notification-runtime",
        "BARK_PUSH_URL",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "--request POST",
        RECEIPT_BUILDER.name,
        RECEIPT_COMMENT.name,
        "issues: write",
    ):
        if forbidden in producer_text:
            errors.append(
                f"terminal completion producer contains forbidden path: {forbidden}"
            )

    auto_text = workflow_text.get(AUTO_RECOVERY, "")
    for forbidden in (
        "      - Devflow Incident\n",
        "      - Devflow Terminal State Notification\n",
        "notification-runtime",
        "BARK_PUSH_URL",
        RECEIPT_BUILDER.name,
        RECEIPT_COMMENT.name,
    ):
        if forbidden in auto_text:
            errors.append(
                f"Auto Recovery contains forbidden notification retry path: {forbidden}"
            )
    for fragment in (
        "notification_event.py resolve-task",
        "value['task_id'] = resolved['task_id']",
        "TERMINAL_NOTIFICATION_TASK_ID=RESOLVED_FROM_CANONICAL_STATE",
        "AUTOMATIC_BARK_RETRIES=0",
    ):
        if fragment not in auto_text:
            errors.append(
                f"Auto Recovery missing terminal task binding: {fragment}"
            )

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "notification_runtime_workflows": environment_users,
        "bark_secret_workflows": secret_users,
        "bark_receipt_workflows": receipt_script_users,
        "completion_scanner_workflows": scanner_users,
        "completion_producer": TERMINAL_PRODUCER.as_posix(),
        "stable_completion_marker": canonical_issue.get(
            "stable_completion_marker"
        ),
        "completion_delivery_fail_open": not errors,
        "bark_post_locations": incident_text.count("--request POST"),
        "bark_receipt_artifact_uploads": incident_text.count(
            "actions/upload-artifact@"
        ),
        "bark_receipt_retention_days": receipt.get("retention_days"),
        "bark_receipt_issue_index": receipt.get("issue_index_enabled"),
        "raw_workflow_failure_notifications": 0 if not errors else None,
        "automatic_bark_retries": 0 if not errors else None,
        "allowed_bark_schemes": bark.get("allowed_schemes"),
        "one_time_live_retest": live_retest,
        "errors": errors,
    }
    return summary


def main() -> int:
    summary = validate()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
