from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import pytest

from ashare_f10.api.ascope_batches import (
    AscopeBatchManager,
    CreateAscopeBatchRequest,
)


def _wait_terminal(manager: AscopeBatchManager, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.get(job_id)
        if state["status"] in {
            "COMPLETED",
            "COMPLETED_WITH_GAPS",
            "FAILED_RECOVERABLE",
            "FAILED_TERMINAL",
            "CANCELLED",
        }:
            return state
        time.sleep(0.1)
    raise AssertionError(f"job did not become terminal: {manager.get(job_id)}")


def _fixture_request(root: Path) -> str:
    source = root / "requests" / "fixture"
    batches = source / "financial_batches"
    batches.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "ascope_bridge"
    (source / "financial_request_manifest.json").write_bytes(
        (fixture / "financial_request_manifest.json").read_bytes()
    )
    (batches / "B001.csv").write_bytes((fixture / "B001_smoke_5.csv").read_bytes())
    return source.name


def test_api_manager_rejects_request_path_escape(tmp_path: Path) -> None:
    manager = AscopeBatchManager(tmp_path / "bridge")
    with pytest.raises(ValueError, match="one file or directory name"):
        manager._safe_request_path("../outside.zip")


def test_api_manager_recovers_interrupted_state(tmp_path: Path) -> None:
    root = tmp_path / "bridge"
    job_dir = root / "jobs" / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "status": "RUNNING",
                "request": {"batch_id": "B001"},
                "updated_at_utc": "2026-07-30T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    manager = AscopeBatchManager(root)
    state = manager.get("job-1")
    assert state["status"] == "FAILED_RECOVERABLE"
    assert state["retryable"] is True
    assert state["error_code"] == "API_PROCESS_RESTARTED"


def test_api_manager_fixture_job_persists_and_completes(tmp_path: Path) -> None:
    root = tmp_path / "bridge"
    manager = AscopeBatchManager(root, project_root=Path(__file__).resolve().parents[1])
    request_name = _fixture_request(root)
    state = manager.create(
        CreateAscopeBatchRequest(
            request_package=request_name,
            batch_id="B001",
            as_of_date=date(2026, 7, 30),
            smoke_count=5,
            fixture_mode=True,
        )
    )
    final = _wait_terminal(manager, state["job_id"])
    assert final["status"] == "COMPLETED"
    output = Path(final["output_root"]) / "B001"
    manifest = json.loads((output / "batch_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PASS"
    assert manifest["fixture_mode"] is True
    assert manifest["non_investment_output"] is True
    assert manager.read_log(state["job_id"])["next_offset"] > 0


def test_api_cancel_preserves_existing_checkpoint(tmp_path: Path) -> None:
    root = tmp_path / "bridge"
    request_file = root / "requests" / "dummy.zip"
    request_file.parent.mkdir(parents=True)
    request_file.write_bytes(b"fixture")

    def command_builder(_state: dict, output_root: Path) -> list[str]:
        checkpoint = output_root / "B001" / "checkpoint.json"
        program = (
            "from pathlib import Path; import time; "
            f"p=Path({str(checkpoint)!r}); p.parent.mkdir(parents=True, exist_ok=True); "
            "p.write_text('checkpoint', encoding='utf-8'); time.sleep(30)"
        )
        return [sys.executable, "-c", program]

    manager = AscopeBatchManager(
        root,
        project_root=Path(__file__).resolve().parents[1],
        command_builder=command_builder,
    )
    created = manager.create(
        CreateAscopeBatchRequest(
            request_package=request_file.name,
            batch_id="B001",
            as_of_date=date(2026, 7, 30),
        )
    )
    checkpoint = Path(created["output_root"]) / "B001" / "checkpoint.json"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not checkpoint.exists():
        time.sleep(0.05)
    assert checkpoint.exists()
    manager.cancel(created["job_id"])
    final = _wait_terminal(manager, created["job_id"], timeout=10)
    assert final["status"] == "CANCELLED"
    assert final["retryable"] is True
    assert checkpoint.read_text(encoding="utf-8") == "checkpoint"
