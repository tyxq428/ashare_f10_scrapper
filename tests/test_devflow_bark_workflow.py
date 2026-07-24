from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCIDENT = ROOT / ".github/workflows/devflow-incident.yml"
AUTO_RECOVERY = ROOT / ".github/workflows/devflow-auto-recovery.yml"


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


def test_auto_recovery_does_not_monitor_incident_or_bark_delivery() -> None:
    text = AUTO_RECOVERY.read_text(encoding="utf-8")
    assert "      - Devflow Incident\n" not in text
    assert "notification-runtime" not in text
    assert "BARK_PUSH_URL" not in text
