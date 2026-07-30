from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ashare_f10.ascope_bridge.batch import (
    BatchExecutionError,
    StockProcessResult,
    run_batch,
)


@dataclass
class Manifest:
    through: str = "2026-07-30"


@dataclass
class Resolved:
    batch_id: str
    rows: tuple[dict, ...]
    package_sha256: str = "package"
    selected_batch_sha256: str = "batch"
    source_row_count: int = 3
    smoke_count: int = 0
    manifest: Manifest = field(default_factory=Manifest)


def request_rows(count: int = 3) -> tuple[dict, ...]:
    return tuple(
        {
            "batch_id": "B001",
            "security_id": f"SZSE.{index:06d}",
            "code": f"{index:06d}",
            "name": f"N{index}",
            "exchange": "SZSE",
            "request_annual_from": "2019-12-31",
            "request_quarterly_from": "2022-03-31",
            "request_through": "2026-07-30",
            "required_available_at": True,
            "request_status": "PENDING",
        }
        for index in range(1, count + 1)
    )


def test_retry_then_resume_preserves_completed(tmp_path: Path) -> None:
    resolved = Resolved("B001", request_rows())
    calls: dict[str, int] = {}

    def first(row: dict, _attempt: int, _context: dict) -> StockProcessResult:
        security_id = row["security_id"]
        calls[security_id] = calls.get(security_id, 0) + 1
        if security_id.endswith("000002"):
            return StockProcessResult(
                "FAILED_RETRYABLE", True, "TEMP", "temporary"
            )
        return StockProcessResult("COMPLETED")

    result = run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=first,
        max_attempts=1,
        heartbeat_seconds=0.01,
    )
    assert result.status == "FAILED_RECOVERABLE"
    assert result.completed_count == 2

    second_calls: list[str] = []

    def second(row: dict, _attempt: int, _context: dict) -> StockProcessResult:
        second_calls.append(row["security_id"])
        return StockProcessResult("COMPLETED")

    resumed = run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=second,
        max_attempts=2,
        heartbeat_seconds=0.01,
    )
    assert resumed.status == "PASS"
    assert second_calls == ["SZSE.000002"]


def test_concurrency_is_bounded_at_two(tmp_path: Path) -> None:
    resolved = Resolved("B001", request_rows(5), source_row_count=5)
    lock = threading.Lock()
    active = 0
    maximum = 0

    def processor(
        _row: dict, _attempt: int, _context: dict
    ) -> StockProcessResult:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return StockProcessResult("COMPLETED")

    result = run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=processor,
        max_stock_workers=2,
        heartbeat_seconds=0.01,
    )
    assert result.status == "PASS"
    assert maximum == 2


def test_attempts_stop_at_two(tmp_path: Path) -> None:
    resolved = Resolved("B001", request_rows(1), source_row_count=1)
    calls: list[int] = []

    def processor(
        _row: dict, attempt: int, _context: dict
    ) -> StockProcessResult:
        calls.append(attempt)
        return StockProcessResult(
            "FAILED_RETRYABLE", True, "TEMP", "temporary"
        )

    result = run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=processor,
        max_attempts=2,
        heartbeat_seconds=0.01,
    )
    assert result.failed_retryable_count == 1
    assert calls == [1, 2]


def test_checkpoint_fingerprint_mismatch_fails_closed(tmp_path: Path) -> None:
    resolved = Resolved("B001", request_rows(1), source_row_count=1)
    run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=lambda *_args: StockProcessResult("COMPLETED"),
        heartbeat_seconds=0.01,
    )
    changed = Resolved(
        "B001",
        request_rows(1),
        package_sha256="changed",
        source_row_count=1,
    )
    with pytest.raises(BatchExecutionError) as error:
        run_batch(
            changed,
            data_root=tmp_path / "data",
            output_root=tmp_path / "out",
            processor=lambda *_args: StockProcessResult("COMPLETED"),
        )
    assert error.value.code == "CHECKPOINT_FINGERPRINT_MISMATCH"


def test_inflight_checkpoint_is_resumed_as_retryable(tmp_path: Path) -> None:
    resolved = Resolved("B001", request_rows(1), source_row_count=1)
    output = tmp_path / "out" / "B001"
    output.mkdir(parents=True)
    run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=lambda *_args: StockProcessResult("FAILED_RETRYABLE", True),
        max_attempts=1,
    )
    checkpoint = output / "checkpoint.json"
    value = json.loads(checkpoint.read_text(encoding="utf-8"))
    value["stocks"][0]["status"] = "FETCHING"
    checkpoint.write_text(json.dumps(value), encoding="utf-8")
    calls: list[int] = []

    def processor(
        _row: dict, attempt: int, _context: dict
    ) -> StockProcessResult:
        calls.append(attempt)
        return StockProcessResult("COMPLETED")

    result = run_batch(
        resolved,
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        processor=processor,
        max_attempts=2,
    )
    assert result.status == "PASS"
    assert calls == [2]
