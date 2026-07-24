from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_NOTIFICATION_TYPES = {
    "COMPLETED",
    "INTERRUPTED",
    "HUMAN_REQUIRED",
    "SECURITY_BLOCKED",
}
ALLOWED_DELIVERY_STATUSES = {
    "DELIVERED",
    "FAILED",
    "SKIPPED_MISSING_CONFIGURATION",
}
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,119}$")
MARKER_RE = re.compile(r"^devflow-root:[A-Za-z0-9][A-Za-z0-9._:-]{7,159}:(?:COMPLETED|INTERRUPTED|HUMAN_REQUIRED|SECURITY_BLOCKED)$")
UTC_SECOND_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "notification_type",
        "marker",
        "incident_run_id",
        "incident_run_attempt",
        "source_workflow",
        "source_run_id",
        "canonical_issue_number",
        "delivery_status",
        "request_initiated",
        "request_attempts",
        "curl_exit_code",
        "http_status",
        "automatic_retry",
        "response_body_stored",
        "response_headers_stored",
        "endpoint_logged",
        "endpoint_stored",
        "secret_value_stored",
        "raw_error_stored",
        "completed_at_utc",
    }
)


class BarkDeliveryResultError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BarkDeliveryResultError(f"cannot load JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise BarkDeliveryResultError(f"JSON root must be an object: {path}")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BarkDeliveryResultError(f"{field} must be a positive integer")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BarkDeliveryResultError(f"{field} must be a non-negative integer")
    return value


def _optional_int(value: Any, field: str, *, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise BarkDeliveryResultError(f"{field} must be an integer or null")
    if not minimum <= value <= maximum:
        raise BarkDeliveryResultError(
            f"{field} must be between {minimum} and {maximum}"
        )
    return value


def _safe_string(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise BarkDeliveryResultError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise BarkDeliveryResultError(f"{field} must not be empty")
    if len(text) > maximum:
        raise BarkDeliveryResultError(f"{field} exceeds {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise BarkDeliveryResultError(f"{field} contains a control character")
    return text


def _utc_second(value: Any) -> str:
    text = _safe_string(value, "completed_at_utc", maximum=20)
    if not UTC_SECOND_RE.fullmatch(text):
        raise BarkDeliveryResultError(
            "completed_at_utc must use YYYY-MM-DDTHH:MM:SSZ"
        )
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise BarkDeliveryResultError("completed_at_utc must be second-precision UTC")
    return text


def _validated_notification_fields(value: dict[str, Any]) -> dict[str, Any]:
    task_id = _safe_string(value.get("task_id"), "task_id", maximum=120)
    if not TASK_ID_RE.fullmatch(task_id):
        raise BarkDeliveryResultError("task_id has an invalid format")

    notification_type = _safe_string(
        value.get("notification_type"),
        "notification_type",
        maximum=32,
    )
    if notification_type not in ALLOWED_NOTIFICATION_TYPES:
        raise BarkDeliveryResultError("notification_type is not valuable")

    marker = _safe_string(value.get("marker"), "marker", maximum=220)
    if not MARKER_RE.fullmatch(marker):
        raise BarkDeliveryResultError("marker has an invalid format")
    if not marker.endswith(f":{notification_type}"):
        raise BarkDeliveryResultError("marker does not match notification_type")

    source_workflow = _safe_string(
        value.get("source_workflow"),
        "source_workflow",
        maximum=120,
    )
    source_run_id = _positive_int(value.get("source_run_id"), "source_run_id")
    return {
        "task_id": task_id,
        "notification_type": notification_type,
        "marker": marker,
        "source_workflow": source_workflow,
        "source_run_id": source_run_id,
    }


def validate_delivery_result(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != RECEIPT_FIELDS:
        missing = sorted(RECEIPT_FIELDS - set(value))
        extra = sorted(set(value) - RECEIPT_FIELDS)
        raise BarkDeliveryResultError(
            f"delivery receipt field mismatch: missing={missing}, extra={extra}"
        )
    if value.get("schema_version") != 1:
        raise BarkDeliveryResultError("schema_version must be 1")

    notification = _validated_notification_fields(value)
    incident_run_id = _positive_int(value.get("incident_run_id"), "incident_run_id")
    incident_run_attempt = _positive_int(
        value.get("incident_run_attempt"),
        "incident_run_attempt",
    )
    if incident_run_attempt != 1:
        raise BarkDeliveryResultError("incident_run_attempt must be 1")
    canonical_issue_number = _positive_int(
        value.get("canonical_issue_number"),
        "canonical_issue_number",
    )

    delivery_status = _safe_string(
        value.get("delivery_status"),
        "delivery_status",
        maximum=64,
    )
    if delivery_status not in ALLOWED_DELIVERY_STATUSES:
        raise BarkDeliveryResultError("delivery_status is not allowed")

    request_initiated = value.get("request_initiated")
    if not isinstance(request_initiated, bool):
        raise BarkDeliveryResultError("request_initiated must be boolean")
    request_attempts = _non_negative_int(
        value.get("request_attempts"),
        "request_attempts",
    )
    if request_attempts not in {0, 1}:
        raise BarkDeliveryResultError("request_attempts must be 0 or 1")
    curl_exit_code = _optional_int(
        value.get("curl_exit_code"),
        "curl_exit_code",
        minimum=0,
        maximum=255,
    )
    http_status = _optional_int(
        value.get("http_status"),
        "http_status",
        minimum=100,
        maximum=599,
    )

    fixed_false_fields = (
        "automatic_retry",
        "response_body_stored",
        "response_headers_stored",
        "endpoint_logged",
        "endpoint_stored",
        "secret_value_stored",
        "raw_error_stored",
    )
    for field in fixed_false_fields:
        if value.get(field) is not False:
            raise BarkDeliveryResultError(f"{field} must be false")

    completed_at_utc = _utc_second(value.get("completed_at_utc"))

    if delivery_status == "DELIVERED":
        if not request_initiated or request_attempts != 1:
            raise BarkDeliveryResultError(
                "DELIVERED requires one initiated request"
            )
        if curl_exit_code != 0:
            raise BarkDeliveryResultError("DELIVERED requires curl_exit_code=0")
        if http_status is None or not 200 <= http_status <= 299:
            raise BarkDeliveryResultError("DELIVERED requires HTTP 2xx")
    elif delivery_status == "FAILED":
        if not request_initiated or request_attempts != 1:
            raise BarkDeliveryResultError("FAILED requires one initiated request")
        if curl_exit_code is None:
            raise BarkDeliveryResultError("FAILED requires curl_exit_code")
        if curl_exit_code == 0 and http_status is not None and 200 <= http_status <= 299:
            raise BarkDeliveryResultError(
                "FAILED must contain a curl failure or non-2xx HTTP status"
            )
    else:
        if request_initiated or request_attempts != 0:
            raise BarkDeliveryResultError(
                "SKIPPED_MISSING_CONFIGURATION requires zero requests"
            )
        if curl_exit_code is not None or http_status is not None:
            raise BarkDeliveryResultError(
                "SKIPPED_MISSING_CONFIGURATION cannot contain transport status"
            )

    return {
        "schema_version": 1,
        **notification,
        "incident_run_id": incident_run_id,
        "incident_run_attempt": incident_run_attempt,
        "canonical_issue_number": canonical_issue_number,
        "delivery_status": delivery_status,
        "request_initiated": request_initiated,
        "request_attempts": request_attempts,
        "curl_exit_code": curl_exit_code,
        "http_status": http_status,
        "automatic_retry": False,
        "response_body_stored": False,
        "response_headers_stored": False,
        "endpoint_logged": False,
        "endpoint_stored": False,
        "secret_value_stored": False,
        "raw_error_stored": False,
        "completed_at_utc": completed_at_utc,
    }


def build_delivery_result(
    *,
    validated_notification: dict[str, Any],
    incident_run_id: int,
    incident_run_attempt: int,
    canonical_issue_number: int,
    delivery_status: str,
    request_initiated: bool,
    request_attempts: int,
    curl_exit_code: int | None,
    http_status: int | None,
    completed_at_utc: str,
) -> dict[str, Any]:
    notification = _validated_notification_fields(validated_notification)
    value = {
        "schema_version": 1,
        **notification,
        "incident_run_id": incident_run_id,
        "incident_run_attempt": incident_run_attempt,
        "canonical_issue_number": canonical_issue_number,
        "delivery_status": delivery_status,
        "request_initiated": request_initiated,
        "request_attempts": request_attempts,
        "curl_exit_code": curl_exit_code,
        "http_status": http_status,
        "automatic_retry": False,
        "response_body_stored": False,
        "response_headers_stored": False,
        "endpoint_logged": False,
        "endpoint_stored": False,
        "secret_value_stored": False,
        "raw_error_stored": False,
        "completed_at_utc": completed_at_utc,
    }
    return validate_delivery_result(value)


def _parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("boolean value must be true or false")


def _parse_optional_cli_int(value: str) -> int | None:
    if value == "null":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer or null") from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_summary(value: dict[str, Any]) -> None:
    http_status = value["http_status"]
    print(f"BARK_DELIVERY_STATUS={value['delivery_status']}")
    print(
        "BARK_REQUEST_INITIATED="
        f"{'true' if value['request_initiated'] else 'false'}"
    )
    print(f"BARK_REQUEST_ATTEMPTS={value['request_attempts']}")
    print(f"BARK_HTTP_STATUS={'' if http_status is None else http_status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--validated-notification", type=Path, required=True)
    build_parser.add_argument("--incident-run-id", type=int, required=True)
    build_parser.add_argument("--incident-run-attempt", type=int, required=True)
    build_parser.add_argument("--canonical-issue-number", type=int, required=True)
    build_parser.add_argument(
        "--delivery-status",
        choices=sorted(ALLOWED_DELIVERY_STATUSES),
        required=True,
    )
    build_parser.add_argument(
        "--request-initiated",
        type=_parse_bool,
        required=True,
    )
    build_parser.add_argument("--request-attempts", type=int, required=True)
    build_parser.add_argument(
        "--curl-exit-code",
        type=_parse_optional_cli_int,
        default=None,
    )
    build_parser.add_argument(
        "--http-status",
        type=_parse_optional_cli_int,
        default=None,
    )
    build_parser.add_argument("--completed-at-utc", required=True)
    build_parser.add_argument("--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "validate":
        value = validate_delivery_result(_load_object(args.input))
        _print_summary(value)
        return 0

    value = build_delivery_result(
        validated_notification=_load_object(args.validated_notification),
        incident_run_id=args.incident_run_id,
        incident_run_attempt=args.incident_run_attempt,
        canonical_issue_number=args.canonical_issue_number,
        delivery_status=args.delivery_status,
        request_initiated=args.request_initiated,
        request_attempts=args.request_attempts,
        curl_exit_code=args.curl_exit_code,
        http_status=args.http_status,
        completed_at_utc=args.completed_at_utc,
    )
    _write_json(args.output, value)
    _print_summary(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
