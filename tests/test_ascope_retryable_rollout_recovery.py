from __future__ import annotations

import json
from pathlib import Path

import pytest

from ashare_f10.recovery.ascope_retryable_checkpoint import reset_retryable_failures
from ashare_f10.recovery.ascope_transient_batch import (
    TransientBatchVerificationError,
    verify_recoverable_batch,
    verify_transient_quote_502_batch,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _quote_combined(error: str | None = None) -> dict:
    return {
        "groups": [
            {
                "group_id": "ef08aa02d7e84c00",
                "theme": "行情估值",
                "family": "/api/qt/stock/get",
                "strategy": "union_quote_fields",
                "success": False,
                "record_count": 0,
                "errors": [
                    error
                    or "attempt 1: HTTPError: HTTP 502；"
                    "attempt 2: HTTPError: HTTP 502；"
                    "attempt 3: HTTPError: HTTP 502"
                ],
            },
            {
                "group_id": "other",
                "family": "RPT_F10_FINANCE_GINCOME",
                "strategy": "finance_all_periods",
                "success": True,
                "record_count": 1,
                "errors": [],
            },
        ]
    }


def _batch_fixture(
    root: Path,
    *,
    error: str | None = None,
    terminal: bool = False,
) -> Path:
    batch = root / "B003"
    failed_status = "FAILED_TERMINAL" if terminal else "FAILED_RETRYABLE"
    validation_status = "FAILED_TERMINAL" if terminal else "FAILED_RECOVERABLE"
    _write_json(
        batch / "validation_report.json",
        {
            "schema_version": 1,
            "status": validation_status,
            "batch_id": "B003",
            "as_of_date": "2026-07-30",
            "input_count": 2,
            "successful_count": 1,
            "failed_count": 1,
            "deferred_count": 0,
            "formal_future_rows": 0,
            "conservation_pass": True,
        },
    )
    _write_json(
        batch / "checkpoint.json",
        {
            "schema_version": 1,
            "batch_id": "B003",
            "fingerprint": "fixture",
            "status": validation_status,
            "stocks": [
                {
                    "security_id": "SZSE.001212",
                    "status": "COMPLETED_WITH_GAPS",
                    "attempt_count": 1,
                },
                {
                    "security_id": "SZSE.001213",
                    "status": failed_status,
                    "attempt_count": 2,
                    "retryable": not terminal,
                    "error_code": "F10_FETCH_FAILED",
                    "message": "1 F10 request groups failed",
                    "details": {"report": "resilient-fetch-report.json"},
                },
            ],
        },
    )
    _write_json(
        batch / "_f10_runs" / "SZSE.001213" / "combined.json",
        _quote_combined(error),
    )
    return batch


def _mixed_recoverable_fixture(root: Path) -> Path:
    batch = root / "B004"
    _write_json(
        batch / "validation_report.json",
        {
            "schema_version": 1,
            "status": "FAILED_RECOVERABLE",
            "batch_id": "B004",
            "as_of_date": "2026-07-30",
            "input_count": 3,
            "successful_count": 1,
            "failed_count": 1,
            "deferred_count": 1,
            "formal_future_rows": 0,
            "conservation_pass": True,
        },
    )
    _write_json(
        batch / "checkpoint.json",
        {
            "schema_version": 1,
            "batch_id": "B004",
            "fingerprint": "fixture",
            "status": "FAILED_RECOVERABLE",
            "stocks": [
                {
                    "security_id": "SZSE.001212",
                    "status": "COMPLETED_WITH_GAPS",
                    "attempt_count": 1,
                },
                {
                    "security_id": "SZSE.001213",
                    "status": "FAILED_RETRYABLE",
                    "attempt_count": 2,
                    "retryable": True,
                    "error_code": "F10_FETCH_FAILED",
                    "message": "1 F10 request groups failed",
                    "details": {"report": "resilient-fetch-report.json"},
                },
                {
                    "security_id": "SZSE.001214",
                    "status": "DEFERRED_TIME_BUDGET",
                    "attempt_count": 0,
                    "retryable": True,
                    "error_code": "TIME_BUDGET_REACHED",
                    "message": "Soft deadline reached before another stock attempt",
                    "details": {},
                },
            ],
        },
    )
    _write_json(
        batch / "_f10_runs" / "SZSE.001213" / "combined.json",
        _quote_combined(),
    )
    return batch


def test_verify_and_reset_exact_retryable_quote_502_batch(tmp_path: Path) -> None:
    batch = _batch_fixture(tmp_path)

    verification = verify_transient_quote_502_batch(batch)
    report = reset_retryable_failures(
        batch / "checkpoint.json",
        security_ids=set(verification["security_ids"]),
    )

    checkpoint = json.loads((batch / "checkpoint.json").read_text(encoding="utf-8"))
    successful, recovered = checkpoint["stocks"]
    assert verification["retryable_count"] == 1
    assert verification["deferred_count"] == 0
    assert verification["authorized_root_cause"]["error_class"] == "HTTP_502_ONLY"
    assert (
        verification["evidence"]["quote_http_502"]["SZSE.001213"][
            "http_502_attempt_count"
        ]
        == 3
    )
    assert report["recovered_count"] == 1
    assert report["unchanged_success_count"] == 1
    assert successful["status"] == "COMPLETED_WITH_GAPS"
    assert recovered["status"] == "PENDING"
    assert recovered["attempt_count"] == 0
    assert recovered["error_code"] == ""
    assert recovered["recovery_history"][0]["prior_status"] == "FAILED_RETRYABLE"
    assert recovered["recovery_history"][0]["prior_attempt_count"] == 2


def test_existing_finalizer_call_recovers_mixed_quote_and_deadline_set(
    tmp_path: Path,
) -> None:
    batch = _mixed_recoverable_fixture(tmp_path)

    verification = verify_transient_quote_502_batch(batch)
    reset = reset_retryable_failures(
        batch / "checkpoint.json",
        security_ids=set(verification["security_ids"]),
        expected_error_code="F10_FETCH_FAILED",
        reason=(
            "verified /api/qt/stock/get union_quote_fields outage; "
            "HTTP 502 only; post-rollout bounded retry authorized"
        ),
    )

    assert verification["retryable_count"] == 1
    assert verification["deferred_count"] == 1
    assert verification["security_ids"] == ["SZSE.001213", "SZSE.001214"]
    assert verification["authorized_root_cause"]["error_class"] == (
        "APPROVED_RECOVERABLE_SET"
    )
    assert verification["authorized_root_causes"] == [
        {
            "status": "FAILED_RETRYABLE",
            "group_id": "ef08aa02d7e84c00",
            "family": "/api/qt/stock/get",
            "strategy": "union_quote_fields",
            "error_class": "HTTP_502_ONLY",
            "security_count": 1,
        },
        {
            "status": "DEFERRED_TIME_BUDGET",
            "error_code": "TIME_BUDGET_REACHED",
            "error_class": "SOFT_DEADLINE_ONLY",
            "security_count": 1,
        },
    ]
    assert reset["recovered_count"] == 2
    assert reset["unchanged_success_count"] == 1

    checkpoint = json.loads((batch / "checkpoint.json").read_text(encoding="utf-8"))
    states = {item["security_id"]: item for item in checkpoint["stocks"]}
    assert states["SZSE.001212"]["status"] == "COMPLETED_WITH_GAPS"
    assert states["SZSE.001213"]["status"] == "PENDING"
    assert states["SZSE.001214"]["status"] == "PENDING"
    deferred_history = states["SZSE.001214"]["recovery_history"][0]
    assert deferred_history["prior_error_code"] == "TIME_BUDGET_REACHED"
    assert "soft-deadline deferral" in deferred_history["reason"]
    assert "HTTP 502 only" not in deferred_history["reason"]


def test_explicit_recoverable_verifier_reports_mixed_root_causes(
    tmp_path: Path,
) -> None:
    batch = _mixed_recoverable_fixture(tmp_path)

    verification = verify_recoverable_batch(batch)

    assert verification["retryable_security_ids"] == ["SZSE.001213"]
    assert verification["deferred_security_ids"] == ["SZSE.001214"]
    assert verification["security_ids"] == ["SZSE.001213", "SZSE.001214"]


def test_recoverable_verifier_rejects_unapproved_deferred_state(
    tmp_path: Path,
) -> None:
    batch = _mixed_recoverable_fixture(tmp_path)
    checkpoint_path = batch / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["stocks"][2]["error_code"] = "OTHER_ERROR"
    _write_json(checkpoint_path, checkpoint)

    with pytest.raises(
        TransientBatchVerificationError,
        match="unexpected error_code",
    ):
        verify_transient_quote_502_batch(batch)


def test_verifier_rejects_non_502_or_terminal_failure(tmp_path: Path) -> None:
    non_502 = _batch_fixture(
        tmp_path / "non-502",
        error="attempt 1: HTTPError: HTTP 429",
    )
    with pytest.raises(TransientBatchVerificationError, match="not exclusively HTTP 502"):
        verify_transient_quote_502_batch(non_502)

    terminal = _batch_fixture(tmp_path / "terminal", terminal=True)
    with pytest.raises(TransientBatchVerificationError, match="not FAILED_RECOVERABLE"):
        verify_transient_quote_502_batch(terminal)


def test_reset_requires_exact_retryable_set_and_error_code(tmp_path: Path) -> None:
    batch = _batch_fixture(tmp_path)
    checkpoint = batch / "checkpoint.json"

    with pytest.raises(ValueError, match="does not match checkpoint retryable failures"):
        reset_retryable_failures(
            checkpoint,
            security_ids={"SZSE.001213", "SZSE.001215"},
        )

    with pytest.raises(ValueError, match="expected 'OTHER_ERROR'"):
        reset_retryable_failures(
            checkpoint,
            security_ids={"SZSE.001213"},
            expected_error_code="OTHER_ERROR",
        )
