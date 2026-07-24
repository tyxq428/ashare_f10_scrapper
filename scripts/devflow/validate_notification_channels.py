from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST = Path(".devflow/notification-channels.yaml")
WORKFLOW_ROOT = Path(".github/workflows")
INCIDENT = WORKFLOW_ROOT / "devflow-incident.yml"
TERMINAL_STATE = WORKFLOW_ROOT / "devflow-terminal-state-notify.yml"
AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"


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
    bark: dict[str, Any] = {}
    if not isinstance(channels, dict):
        errors.append("notification channels must be an object")
    else:
        value = channels.get("bark")
        if not isinstance(value, dict):
            errors.append("Bark channel policy is missing")
        else:
            bark = value
    expected_bark = {
        "enabled": True,
        "environment": "notification-runtime",
        "secret_name": "BARK_PUSH_URL",
        "automatic_retry": False,
        "github_rerun_resend": False,
        "run_attempt_must_equal": 1,
        "maximum_requests_per_notification": 1,
        "failure_changes_task_state": False,
    }
    for key, expected in expected_bark.items():
        if bark.get(key) != expected:
            errors.append(f"Bark policy mismatch for {key}")

    producer = manifest.get("completion_producer")
    if not isinstance(producer, dict):
        errors.append("completion producer policy is missing")
    else:
        if producer.get("workflow") != TERMINAL_STATE.as_posix():
            errors.append("completion producer workflow mismatch")
        if producer.get("strict_done_required") is not True:
            errors.append("completion producer must require strict DONE")

    workflow_text: dict[Path, str] = {}
    for path in sorted(WORKFLOW_ROOT.glob("*.yml")):
        workflow_text[path] = path.read_text(encoding="utf-8")

    environment_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if "notification-runtime" in text
    ]
    if environment_users != [INCIDENT.as_posix()]:
        errors.append(
            "notification-runtime must be referenced only by Devflow Incident: "
            f"{environment_users}"
        )

    secret_users = [
        path.as_posix()
        for path, text in workflow_text.items()
        if "${{ secrets.BARK_PUSH_URL }}" in text
    ]
    if secret_users != [INCIDENT.as_posix()]:
        errors.append(
            "BARK_PUSH_URL must be referenced only by Devflow Incident: "
            f"{secret_users}"
        )

    incident_text = workflow_text.get(INCIDENT, "")
    required_incident = (
        "repository_dispatch:",
        "devflow_notify",
        "notification_event.py prepare",
        "github.run_attempt == 1",
        "continue-on-error: true",
        "--retry 0",
        "--output /dev/null",
        "BARK_DELIVERY=FAILED_FAIL_OPEN",
        "BARK_AUTOMATIC_RETRIES=0",
        "BARK_REQUESTS_PER_LOGICAL_NOTIFICATION_MAX=1",
    )
    for fragment in required_incident:
        if fragment not in incident_text:
            errors.append(f"Devflow Incident missing Bark guard: {fragment}")
    if incident_text.count("--request POST") != 1:
        errors.append("Devflow Incident must contain exactly one Bark POST location")
    for forbidden in (
        "workflow_run:",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "private_responses_forwarder.py",
        "relay_health.py",
    ):
        if forbidden in incident_text:
            errors.append(f"Devflow Incident contains forbidden path: {forbidden}")

    terminal_text = workflow_text.get(TERMINAL_STATE, "")
    for fragment in (
        "push:",
        "      - main",
        "docs/implementation/*/task_state.yaml",
        "terminal_notification_scan.py",
        "devflow_notify",
        "persist-credentials: false",
        "BARK_REQUESTS_IN_THIS_WORKFLOW=0",
    ):
        if fragment not in terminal_text:
            errors.append(f"terminal state producer missing guard: {fragment}")
    for forbidden in (
        "workflow_run:",
        "notification-runtime",
        "BARK_PUSH_URL",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "--request POST",
    ):
        if forbidden in terminal_text:
            errors.append(f"terminal state producer contains forbidden path: {forbidden}")

    auto_text = workflow_text.get(AUTO_RECOVERY, "")
    for forbidden in (
        "      - Devflow Incident\n",
        "      - Devflow Terminal State Notification\n",
        "notification-runtime",
        "BARK_PUSH_URL",
    ):
        if forbidden in auto_text:
            errors.append(f"Auto Recovery contains forbidden notification retry path: {forbidden}")
    for fragment in (
        "notification_event.py resolve-task",
        "value['task_id'] = resolved['task_id']",
        "TERMINAL_NOTIFICATION_TASK_ID=RESOLVED_FROM_CANONICAL_STATE",
        "AUTOMATIC_BARK_RETRIES=0",
    ):
        if fragment not in auto_text:
            errors.append(f"Auto Recovery missing terminal task binding: {fragment}")

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "notification_runtime_workflows": environment_users,
        "bark_secret_workflows": secret_users,
        "bark_post_locations": incident_text.count("--request POST"),
        "raw_workflow_run_notifications": 0 if not errors else None,
        "automatic_bark_retries": 0 if not errors else None,
        "errors": errors,
    }
    return summary


def main() -> int:
    summary = validate()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
