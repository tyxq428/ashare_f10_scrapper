from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit

from bark_delivery_result import (
    BarkDeliveryResultError,
    _load_object,
    _positive_int,
    validate_delivery_result,
)

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALLOWED_UPLOAD_STATUSES = {"UPLOADED", "FAILED"}


class BarkDeliveryReceiptCommentError(ValueError):
    pass


def _artifact_url(
    value: str,
    *,
    repository: str,
    incident_run_id: int,
    artifact_id: int,
) -> str:
    parsed = urlsplit(value)
    expected_path = (
        f"/{repository}/actions/runs/{incident_run_id}/artifacts/{artifact_id}"
    )
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.path.rstrip("/") != expected_path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise BarkDeliveryReceiptCommentError(
            "artifact_url must identify the exact current-repository Artifact"
        )
    return value


def render_receipt_comment(
    *,
    receipt: dict[str, object],
    repository: str,
    artifact_upload_status: str,
    artifact_id: int | None,
    artifact_url: str | None,
) -> str:
    try:
        validated = validate_delivery_result(receipt)
    except BarkDeliveryResultError as exc:
        raise BarkDeliveryReceiptCommentError(str(exc)) from exc

    if not REPOSITORY_RE.fullmatch(repository):
        raise BarkDeliveryReceiptCommentError(
            "repository must use owner/name format"
        )
    if artifact_upload_status not in ALLOWED_UPLOAD_STATUSES:
        raise BarkDeliveryReceiptCommentError(
            "artifact_upload_status must be UPLOADED or FAILED"
        )

    artifact_line: str
    if artifact_upload_status == "UPLOADED":
        if artifact_id is None or artifact_url is None:
            raise BarkDeliveryReceiptCommentError(
                "UPLOADED requires artifact_id and artifact_url"
            )
        normalized_id = _positive_int(artifact_id, "artifact_id")
        normalized_url = _artifact_url(
            artifact_url,
            repository=repository,
            incident_run_id=validated["incident_run_id"],
            artifact_id=normalized_id,
        )
        artifact_line = f"- Receipt Artifact: [{normalized_id}]({normalized_url})"
    else:
        if artifact_id is not None or artifact_url is not None:
            raise BarkDeliveryReceiptCommentError(
                "FAILED artifact upload cannot include artifact metadata"
            )
        artifact_line = "- Receipt Artifact: unavailable (upload failed open)"

    http_status = validated["http_status"]
    curl_exit_code = validated["curl_exit_code"]
    incident_url = (
        f"https://github.com/{repository}/actions/runs/"
        f"{validated['incident_run_id']}"
    )
    marker = f"devflow-bark-delivery-receipt:{validated['marker']}"
    return "\n".join(
        (
            "[BARK][DELIVERY_RECEIPT]",
            "",
            f"- Task: `{validated['task_id']}`",
            f"- Notification: `{validated['notification_type']}`",
            f"- Delivery status: `{validated['delivery_status']}`",
            "- Request initiated: "
            f"`{'true' if validated['request_initiated'] else 'false'}`",
            f"- Request attempts: `{validated['request_attempts']}`",
            "- Curl exit code: "
            f"`{'none' if curl_exit_code is None else curl_exit_code}`",
            "- HTTP status: "
            f"`{'none' if http_status is None else http_status}`",
            f"- Incident Run: {incident_url}",
            artifact_line,
            f"- Artifact upload: `{artifact_upload_status}`",
            "- Safety: response body, response headers, endpoint diagnostics, "
            "raw errors and Secret values were not stored.",
            "",
            f"<!-- {marker} -->",
        )
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--artifact-upload-status",
        choices=sorted(ALLOWED_UPLOAD_STATUSES),
        required=True,
    )
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--artifact-url")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    comment = render_receipt_comment(
        receipt=_load_object(args.receipt),
        repository=args.repository,
        artifact_upload_status=args.artifact_upload_status,
        artifact_id=args.artifact_id,
        artifact_url=args.artifact_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(comment, encoding="utf-8")
    print(f"BARK_RECEIPT_COMMENT_STATUS={args.artifact_upload_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
