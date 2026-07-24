from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from bark_delivery_result import (  # noqa: E402
    RECEIPT_FIELDS,
    BarkDeliveryResultError,
    build_delivery_result,
    validate_delivery_result,
)


def _validated_notification() -> dict[str, object]:
    return {
        "task_id": "sample-task",
        "notification_type": "COMPLETED",
        "marker": "devflow-root:task-completed:sample-task:g1:COMPLETED",
        "source_workflow": "Devflow State Consistency",
        "source_run_id": 1001,
    }


def _build(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "validated_notification": _validated_notification(),
        "incident_run_id": 2001,
        "incident_run_attempt": 1,
        "canonical_issue_number": 77,
        "delivery_status": "DELIVERED",
        "request_initiated": True,
        "request_attempts": 1,
        "curl_exit_code": 0,
        "http_status": 200,
        "completed_at_utc": "2026-07-24T12:00:00Z",
    }
    values.update(overrides)
    return build_delivery_result(**values)  # type: ignore[arg-type]


def test_delivered_receipt_is_strict_and_secret_free() -> None:
    value = _build()
    assert set(value) == RECEIPT_FIELDS
    assert value["delivery_status"] == "DELIVERED"
    assert value["request_initiated"] is True
    assert value["request_attempts"] == 1
    assert value["curl_exit_code"] == 0
    assert value["http_status"] == 200
    assert value["automatic_retry"] is False
    assert value["response_body_stored"] is False
    assert value["response_headers_stored"] is False
    assert value["endpoint_logged"] is False
    assert value["endpoint_stored"] is False
    assert value["secret_value_stored"] is False
    assert value["raw_error_stored"] is False
    serialized = json.dumps(value, sort_keys=True)
    for forbidden in (
        "BARK_PUSH_URL",
        "https://",
        "hostname",
        "response_body",
        "response_headers",
        "api_key",
        "device_key",
    ):
        if forbidden in {"response_body", "response_headers"}:
            continue
        assert forbidden not in serialized


def test_failed_receipt_accepts_curl_transport_failure() -> None:
    value = _build(
        delivery_status="FAILED",
        curl_exit_code=28,
        http_status=None,
    )
    assert value["request_initiated"] is True
    assert value["request_attempts"] == 1
    assert value["curl_exit_code"] == 28
    assert value["http_status"] is None


def test_failed_receipt_accepts_non_2xx_http_status() -> None:
    value = _build(
        delivery_status="FAILED",
        curl_exit_code=22,
        http_status=503,
    )
    assert value["delivery_status"] == "FAILED"
    assert value["http_status"] == 503


def test_missing_configuration_receipt_records_zero_requests() -> None:
    value = _build(
        delivery_status="SKIPPED_MISSING_CONFIGURATION",
        request_initiated=False,
        request_attempts=0,
        curl_exit_code=None,
        http_status=None,
    )
    assert value["request_initiated"] is False
    assert value["request_attempts"] == 0
    assert value["curl_exit_code"] is None
    assert value["http_status"] is None




def test_invalid_configuration_receipt_records_zero_requests() -> None:
    value = _build(
        delivery_status="SKIPPED_INVALID_CONFIGURATION",
        request_initiated=False,
        request_attempts=0,
        curl_exit_code=None,
        http_status=None,
    )
    assert value["delivery_status"] == "SKIPPED_INVALID_CONFIGURATION"
    assert value["request_initiated"] is False
    assert value["request_attempts"] == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"request_attempts": 0},
        {"curl_exit_code": 7},
        {"http_status": 500},
        {"incident_run_attempt": 2},
    ],
)
def test_delivered_receipt_rejects_inconsistent_values(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(BarkDeliveryResultError):
        _build(**overrides)


def test_failed_receipt_rejects_successful_transport() -> None:
    with pytest.raises(BarkDeliveryResultError, match="FAILED must contain"):
        _build(delivery_status="FAILED")


def test_skipped_receipt_rejects_transport_values() -> None:
    with pytest.raises(BarkDeliveryResultError, match="zero requests"):
        _build(
            delivery_status="SKIPPED_MISSING_CONFIGURATION",
            request_initiated=True,
            request_attempts=1,
            curl_exit_code=None,
            http_status=None,
        )


def test_receipt_rejects_non_utc_or_fractional_timestamp() -> None:
    for value in (
        "2026-07-24T12:00:00+00:00",
        "2026-07-24T12:00:00.100Z",
        "2026-07-24T12:00:00+08:00",
    ):
        with pytest.raises(BarkDeliveryResultError, match="completed_at_utc"):
            _build(completed_at_utc=value)


def test_receipt_rejects_extra_or_missing_fields() -> None:
    valid = _build()
    extra = valid | {"endpoint": "forbidden"}
    with pytest.raises(BarkDeliveryResultError, match="field mismatch"):
        validate_delivery_result(extra)
    missing = dict(valid)
    missing.pop("http_status")
    with pytest.raises(BarkDeliveryResultError, match="field mismatch"):
        validate_delivery_result(missing)


def test_receipt_round_trip_validation(tmp_path: Path) -> None:
    path = tmp_path / "bark-delivery-result.json"
    value = _build()
    path.write_text(json.dumps(value), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert validate_delivery_result(loaded) == value


def test_marker_must_match_notification_type() -> None:
    notification = _validated_notification()
    notification["notification_type"] = "INTERRUPTED"
    with pytest.raises(BarkDeliveryResultError, match="marker"):
        _build(validated_notification=notification)
