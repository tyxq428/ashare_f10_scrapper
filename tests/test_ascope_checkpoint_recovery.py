from __future__ import annotations

import json
from pathlib import Path

import pytest

from ashare_f10.recovery.ascope_checkpoint import reset_terminal_failures


def _checkpoint(path: Path) -> None:
    value = {
        "schema_version": 1,
        "batch_id": "B001",
        "fingerprint": "fixture",
        "status": "FAILED_TERMINAL",
        "created_at_utc": "2026-07-30T14:20:00Z",
        "updated_at_utc": "2026-07-30T16:25:00Z",
        "stocks": [
            {
                "security_id": "SZSE.000001",
                "status": "COMPLETED_WITH_GAPS",
                "attempt_count": 1,
            },
            {
                "security_id": "SZSE.000403",
                "status": "FAILED_TERMINAL",
                "attempt_count": 1,
                "error_code": "F10_FETCH_FAILED",
                "message": "unclassified exit code 1",
                "details": {"report": "report.json"},
            },
        ],
    }
    path.write_text(json.dumps(value), encoding="utf-8")


def test_reset_terminal_failure_is_explicit_and_audited(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    _checkpoint(checkpoint)

    report = reset_terminal_failures(
        checkpoint,
        security_ids={"SZSE.000403"},
    )

    value = json.loads(checkpoint.read_text(encoding="utf-8"))
    failed = value["stocks"][1]
    assert report["recovered_count"] == 1
    assert value["status"] == "RUNNING"
    assert value["stocks"][0]["status"] == "COMPLETED_WITH_GAPS"
    assert failed["status"] == "PENDING"
    assert failed["attempt_count"] == 0
    assert failed["error_code"] == ""
    assert failed["recovery_history"][0]["prior_status"] == "FAILED_TERMINAL"
    assert failed["recovery_history"][0]["prior_error_code"] == "F10_FETCH_FAILED"


def test_reset_rejects_an_unmatched_or_different_failure(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    _checkpoint(checkpoint)

    with pytest.raises(ValueError, match="does not match checkpoint terminal failures"):
        reset_terminal_failures(
            checkpoint,
            security_ids={"SZSE.000032", "SZSE.000403"},
        )

    with pytest.raises(ValueError, match="expected 'OTHER_ERROR'"):
        reset_terminal_failures(
            checkpoint,
            security_ids={"SZSE.000403"},
            expected_error_code="OTHER_ERROR",
        )
