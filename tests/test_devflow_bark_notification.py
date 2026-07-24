from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from notification_event import (  # noqa: E402
    NotificationValidationError,
    render_bark_message,
    resolve_task,
    validate_notification,
)
from terminal_notification_scan import scan_terminal_completions  # noqa: E402

REPOSITORY = "tyxq428/ashare_f10_scrapper"


def _state(*, status: str = "RUNNING", generation: int = 0, acknowledged: bool = True) -> dict[str, object]:
    done = status == "DONE"
    return {
        "schema_version": 2,
        "state_revision": generation + 1,
        "task_id": "sample-task",
        "title": "Sample task",
        "status": status,
        "execution_status": "COMPLETED" if done else "RUNNING",
        "acceptance": {
            "domain": "generic",
            "status": "PASS" if done else "PENDING",
            "reason_code": "TASK_COMPLETED" if done else None,
            "details_path": None,
        },
        "security_status": "PASS" if done else "PENDING",
        "working_branch": "main" if done else "feature/sample-task",
        "pull_request": 99,
        "base_sha_at_start": "a" * 40,
        "last_product_commit_sha": "a" * 40,
        "last_state_commit_sha": None,
        "current_stage": "W01",
        "last_completed_stage": "W01" if done else "W00",
        "last_successful_step": "done" if done else "working",
        "next_action": "none" if done else "continue",
        "gate_results": {},
        "retry_budget": {},
        "human_gate": {
            "required": False,
            "reason": None,
            "minimum_action": None,
            "resume_from": None,
        },
        "post_merge": {
            "status": "PASS" if done else "PENDING",
            "merge_sha": "b" * 40 if done else None,
            "verified_run_ids": [123] if done else [],
        },
        "notification": {
            "generation": generation,
            "last_type": "COMPLETED" if done else None,
            "acknowledged": acknowledged,
            "control_issue_number": 7,
        },
        "updated_at_utc": "2026-07-24T00:00:00Z",
    }


def _write_repo(repo: Path, states: list[dict[str, object]]) -> None:
    tasks = []
    for state in states:
        task_id = str(state["task_id"])
        task_dir = repo / "docs/implementation" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task_state.yaml").write_text(json.dumps(state), encoding="utf-8")
        tasks.append(
            {
                "task_id": task_id,
                "title": state["title"],
                "status": state["status"],
                "branch": state["working_branch"],
                "pull_request": state["pull_request"],
                "current_stage": state["current_stage"],
                "state_path": f"docs/implementation/{task_id}/task_state.yaml",
            }
        )
    (repo / "docs/implementation").mkdir(parents=True, exist_ok=True)
    (repo / "docs/implementation/ACTIVE_TASKS.yaml").write_text(
        json.dumps({"schema_version": 1, "tasks": tasks}),
        encoding="utf-8",
    )


def _completed_payload() -> dict[str, object]:
    return {
        "task_id": "sample-task",
        "action": "COMPLETED",
        "notification_type": "COMPLETED",
        "reason_code": "TASK_COMPLETED",
        "reason": "All deterministic gates passed.",
        "minimum_action": "No action is required.",
        "fingerprint": "task-completed:sample-task:g1",
        "source_workflow": "Devflow Terminal State Notification",
        "source_run_id": 123,
        "failure_steps": [],
    }


def test_resolve_explicit_task_and_unique_active_fallback(tmp_path: Path) -> None:
    state = _state()
    _write_repo(tmp_path, [state])
    assert resolve_task(tmp_path, "sample-task").task_id == "sample-task"
    assert resolve_task(tmp_path).task_id == "sample-task"


def test_missing_task_id_fails_when_multiple_tasks_are_active(tmp_path: Path) -> None:
    first = _state()
    second = _state()
    second["task_id"] = "second-task"
    second["title"] = "Second"
    second["working_branch"] = "feature/second-task"
    _write_repo(tmp_path, [first, second])
    with pytest.raises(NotificationValidationError, match="exactly one non-DONE"):
        resolve_task(tmp_path)


def test_completed_event_requires_strict_done_state(tmp_path: Path) -> None:
    _write_repo(tmp_path, [_state()])
    with pytest.raises(NotificationValidationError, match="canonical DONE"):
        validate_notification(repo=tmp_path, repository=REPOSITORY, payload=_completed_payload())


def test_completed_event_and_bark_rendering(tmp_path: Path) -> None:
    _write_repo(tmp_path, [_state(status="DONE", generation=1, acknowledged=False)])
    validated = validate_notification(
        repo=tmp_path,
        repository=REPOSITORY,
        payload=_completed_payload(),
    )
    bark = render_bark_message(validated, repository=REPOSITORY)
    assert validated["control_issue_number"] == 7
    assert validated["marker"] == "devflow-root:task-completed:sample-task:g1:COMPLETED"
    assert bark["level"] == "active"
    assert bark["group"] == "ashare-f10-scrapper-devflow"
    assert bark["url"].endswith("/pull/99")
    assert "sample-task" in bark["body"]


def test_target_url_must_stay_inside_repository(tmp_path: Path) -> None:
    _write_repo(tmp_path, [_state(status="DONE", generation=1, acknowledged=False)])
    payload = _completed_payload()
    payload["target_url"] = "https://example.com/secret"
    with pytest.raises(NotificationValidationError, match="github.com"):
        validate_notification(repo=tmp_path, repository=REPOSITORY, payload=payload)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_state(repo: Path, state: dict[str, object], message: str) -> str:
    _write_repo(repo, [state])
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_terminal_scan_emits_one_new_done_generation(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    before = _commit_state(tmp_path, _state(), "running")
    after = _commit_state(
        tmp_path,
        _state(status="DONE", generation=1, acknowledged=False),
        "done",
    )
    events = scan_terminal_completions(
        repo=tmp_path,
        before=before,
        after=after,
        repository=REPOSITORY,
        source_run_id=555,
    )
    assert len(events) == 1
    assert events[0]["task_id"] == "sample-task"
    assert events[0]["notification_type"] == "COMPLETED"
    assert events[0]["source_run_id"] == 555


def test_terminal_scan_is_silent_for_acknowledged_completion(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    before = _commit_state(tmp_path, _state(), "running")
    after = _commit_state(
        tmp_path,
        _state(status="DONE", generation=1, acknowledged=True),
        "done acknowledged",
    )
    assert scan_terminal_completions(
        repo=tmp_path,
        before=before,
        after=after,
        repository=REPOSITORY,
        source_run_id=556,
    ) == []
