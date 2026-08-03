from __future__ import annotations

import json
from pathlib import Path

import pytest

from ashare_f10.ops.ascope_retryable_recovery import (
    RecoveryContractError,
    inspect_batch,
    plan_rollout_recovery,
    reset_retryable_batch,
)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _success_state(security_id: str) -> dict:
    return {
        "security_id": security_id,
        "status": "COMPLETED_WITH_GAPS",
        "attempt_count": 1,
        "retryable": False,
        "error_code": "",
        "message": "",
        "details": {},
    }


def _failed_state(security_id: str) -> dict:
    return {
        "security_id": security_id,
        "status": "FAILED_RETRYABLE",
        "attempt_count": 2,
        "started_at_utc": "2026-08-03T01:00:00Z",
        "completed_at_utc": "2026-08-03T01:05:00Z",
        "retryable": True,
        "error_code": "F10_FETCH_FAILED",
        "message": "1 F10 request groups failed",
        "details": {"attempt": 2, "report": "resilient-fetch-report.json"},
    }


def _make_batch(
    root: Path,
    batch_id: str,
    *,
    failed_ids: tuple[str, ...] = (),
    bad_group: bool = False,
    terminal: bool = False,
) -> Path:
    batch = root / batch_id
    successful = [_success_state(f"SZSE.{index:06d}") for index in range(1, 4)]
    failed = [_failed_state(value) for value in failed_ids]
    if terminal and failed:
        failed[0]["status"] = "FAILED_TERMINAL"
        failed[0]["retryable"] = False
    stocks = [*successful, *failed]
    _write(
        batch / "checkpoint.json",
        {
            "schema_version": 1,
            "batch_id": batch_id,
            "status": "FAILED_RECOVERABLE" if failed else "PASS_WITH_GAPS",
            "stocks": stocks,
        },
    )
    _write(
        batch / "validation_report.json",
        {
            "schema_version": 1,
            "status": "FAILED_RECOVERABLE" if failed else "PASS_WITH_GAPS",
            "batch_id": batch_id,
            "input_count": len(stocks),
            "successful_count": len(successful),
            "failed_count": len(failed),
            "deferred_count": 0,
            "formal_future_rows": 0,
            "conservation_pass": True,
        },
    )
    for security_id in failed_ids:
        _write(
            batch / "_f10_runs" / security_id / "groups" / "ef08aa02d7e84c00.json",
            {
                "group_id": "other" if bad_group else "ef08aa02d7e84c00",
                "family": "/api/qt/stock/get",
                "strategy": "union_quote_fields",
                "success": False,
                "errors": [
                    "attempt 1: HTTPError: HTTP 502；attempt 2: HTTPError: HTTP 502；"
                    "attempt 3: HTTPError: HTTP 502"
                ],
            },
        )
    return batch


def test_plan_identifies_only_recoverable_batches(tmp_path: Path) -> None:
    _make_batch(tmp_path, "B001")
    _make_batch(tmp_path, "B002", failed_ids=("SZSE.001213", "SZSE.001215"))
    report = plan_rollout_recovery(tmp_path, expected_batches=2)
    assert report["status"] == "READY_FOR_TARGETED_RETRY"
    assert report["success_batches"] == ["B001"]
    assert report["retry_batches"] == ["B002"]
    assert report["retry_matrix"] == {"include": [{"batch_id": "B002"}]}


def test_reset_preserves_successes_and_audits_retryable_states(tmp_path: Path) -> None:
    batch = _make_batch(tmp_path, "B003", failed_ids=("SZSE.001213",))
    report = reset_retryable_batch(batch)
    assert report["status"] == "PASS"
    assert report["reset_count"] == 1
    checkpoint = json.loads((batch / "checkpoint.json").read_text(encoding="utf-8"))
    by_id = {item["security_id"]: item for item in checkpoint["stocks"]}
    assert by_id["SZSE.000001"]["status"] == "COMPLETED_WITH_GAPS"
    recovered = by_id["SZSE.001213"]
    assert recovered["status"] == "PENDING"
    assert recovered["attempt_count"] == 0
    assert recovered["error_code"] == ""
    assert recovered["recovery_history"][-1]["prior_attempt_count"] == 2
    assert recovered["recovery_history"][-1]["evidence"][0]["http_codes"] == ["502"]


def test_terminal_failure_is_rejected(tmp_path: Path) -> None:
    batch = _make_batch(
        tmp_path,
        "B004",
        failed_ids=("SZSE.001213",),
        terminal=True,
    )
    with pytest.raises(RecoveryContractError, match="terminal failures"):
        inspect_batch(batch)


def test_unverified_group_is_rejected(tmp_path: Path) -> None:
    batch = _make_batch(
        tmp_path,
        "B005",
        failed_ids=("SZSE.001213",),
        bad_group=True,
    )
    with pytest.raises(RecoveryContractError, match="outside the verified"):
        inspect_batch(batch)
