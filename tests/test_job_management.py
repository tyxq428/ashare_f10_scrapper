from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ashare_f10.api.jobs import JobManager, extract_security_name
from ashare_f10.config import Settings
from ashare_f10.models import JobGroupState, JobState


class CapturingPool:
    def __init__(self) -> None:
        self.calls = []

    def submit(self, function, *args, **kwargs):
        self.calls.append((function, args, kwargs))
        return object()


def make_manager(tmp_path: Path) -> JobManager:
    return JobManager(Settings(data_dir=tmp_path, max_workers=2, page_workers=1, retries=1))


def make_state(
    manager: JobManager, job_id: str, code: str, name: str, *, status: str = "COMPLETED"
) -> JobState:
    output_dir = manager.settings.data_dir / code / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    state = JobState(
        job_id=job_id,
        stock_code=code,
        stock_name=name,
        status=status,
        created_at_utc="2026-07-20T10:00:00Z",
        updated_at_utc="2026-07-20T10:00:00Z",
        started_at_utc="2026-07-20T10:00:00Z",
        completed_at_utc="2026-07-20T10:01:00Z",
        duration_seconds=60,
        completed_groups=len(manager.group_definitions),
        successful_groups=len(manager.group_definitions),
        total_groups=len(manager.group_definitions),
        failed_groups=0,
        output_dir=str(output_dir),
        artifacts={},
        message="任务完成",
    )
    manager._save(state)
    manager._initialize_group_rows(job_id)
    return state


def test_extract_security_name() -> None:
    payload = {"data": [{"SECURITY_CODE": "300308", "SECURITY_NAME_ABBR": "中际旭创"}]}
    assert extract_security_name(payload, "300308") == "中际旭创"


def test_job_filter_and_stock_code_sort(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    make_state(manager, "job-b", "688041", "海光信息")
    make_state(manager, "job-a", "300308", "中际旭创")

    items, total = manager.query_jobs(q="中际", sort_by="stock_code", sort_direction="asc")
    assert total == 1
    assert items[0].stock_code == "300308"
    assert items[0].stock_name == "中际旭创"

    items, total = manager.query_jobs(sort_by="stock_code", sort_direction="asc")
    assert total == 2
    assert [item.stock_code for item in items] == ["300308", "688041"]


def test_partial_task_cannot_replace_current_complete_version(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    complete = make_state(manager, "complete-job", "300308", "中际旭创")
    manager.set_current(complete.job_id)

    partial = make_state(manager, "partial-job", "300308", "中际旭创", status="PARTIAL")
    partial.failed_groups = 1
    partial.successful_groups -= 1
    manager._save(partial)

    with pytest.raises(ValueError, match="失败0"):
        manager.set_current(partial.job_id)

    pointer = manager.latest("300308")
    assert pointer is not None
    assert pointer["job_id"] == complete.job_id


def test_delete_current_task_removes_folder_and_falls_back(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    older = make_state(manager, "older-job", "300308", "中际旭创")
    older.completed_at_utc = "2026-07-20T10:01:00Z"
    manager._save(older)
    newer = make_state(manager, "newer-job", "300308", "中际旭创")
    newer.completed_at_utc = "2026-07-20T11:01:00Z"
    manager._save(newer)
    manager.set_current(newer.job_id)

    result = manager.delete(newer.job_id, confirm="DELETE")
    assert result["deleted"] is True
    assert not Path(newer.output_dir).exists()
    assert manager.get(newer.job_id) is None
    assert manager.latest("300308")["job_id"] == older.job_id


def test_retry_failed_schedules_only_failed_groups(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    state = make_state(manager, "partial-job", "300308", "中际旭创", status="PARTIAL")
    group_id = next(iter(manager.group_definitions))
    definition = manager.group_definitions[group_id]
    manager._save_group_state(
        JobGroupState(
            job_id=state.job_id,
            group_id=group_id,
            definition_index=definition["definition_index"],
            theme=definition["theme"],
            family=definition["family"],
            strategy=definition["strategy"],
            status="FAILED",
            attempt_count=1,
            errors=["RemoteDisconnected"],
            updated_at_utc="2026-07-20T10:01:00Z",
        )
    )
    state.failed_groups = 1
    state.successful_groups = state.total_groups - 1
    manager._save(state)

    pool = CapturingPool()
    manager.pool = pool
    scheduled = manager.retry_failed(state.job_id)

    assert scheduled.status == "RETRYING"
    assert len(pool.calls) == 1
    _, args, _ = pool.calls[0]
    assert args[0] == state.job_id
    assert args[1] == [group_id]


def test_api_lists_jobs_and_subtasks(monkeypatch, tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    state = make_state(manager, "api-job", "300308", "中际旭创")
    definition = next(iter(manager.group_definitions.values()))
    manager._save_group_state(
        JobGroupState(
            job_id=state.job_id,
            group_id=definition["group_id"],
            definition_index=definition["definition_index"],
            theme=definition["theme"],
            family=definition["family"],
            strategy=definition["strategy"],
            status="SUCCESS",
            record_count=1,
            attempt_count=1,
            updated_at_utc="2026-07-20T10:01:00Z",
        )
    )

    import ashare_f10.api.app as app_module

    monkeypatch.setattr(app_module, "manager", manager)
    client = TestClient(app_module.app)

    response = client.get("/api/jobs", params={"paged": True, "q": "中际", "sort_by": "stock_code"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["stock_name"] == "中际旭创"

    groups = client.get(f"/api/jobs/{state.job_id}/groups", params={"limit": 500})
    assert groups.status_code == 200
    assert groups.json()["total"] == len(manager.group_definitions)


def test_job_state_json_remains_readable_after_schema_upgrade(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    state = make_state(manager, "schema-job", "688041", "海光信息")
    with manager._connect() as connection:
        row = connection.execute("SELECT state_json FROM jobs WHERE job_id=?", (state.job_id,)).fetchone()
    payload = json.loads(row[0])
    assert payload["stock_name"] == "海光信息"
    assert payload["successful_groups"] == len(manager.group_definitions)
