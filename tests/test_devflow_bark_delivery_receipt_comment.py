from __future__ import annotations

import sys
from pathlib import Path

import pytest

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from bark_delivery_receipt_comment import (  # noqa: E402
    BarkDeliveryReceiptCommentError,
    render_receipt_comment,
)
from bark_delivery_result import build_delivery_result  # noqa: E402

REPOSITORY = "tyxq428/ashare_f10_scrapper"


def _receipt() -> dict[str, object]:
    return build_delivery_result(
        validated_notification={
            "task_id": "sample-task",
            "notification_type": "COMPLETED",
            "marker": "devflow-root:task-completed:sample-task:g1:COMPLETED",
            "source_workflow": "Devflow State Consistency",
            "source_run_id": 1001,
        },
        incident_run_id=2001,
        incident_run_attempt=1,
        canonical_issue_number=77,
        delivery_status="DELIVERED",
        request_initiated=True,
        request_attempts=1,
        curl_exit_code=0,
        http_status=200,
        completed_at_utc="2026-07-24T12:00:00Z",
    )


def test_uploaded_receipt_comment_contains_safe_artifact_index() -> None:
    comment = render_receipt_comment(
        receipt=_receipt(),
        repository=REPOSITORY,
        artifact_upload_status="UPLOADED",
        artifact_id=3001,
        artifact_url=(
            "https://github.com/tyxq428/ashare_f10_scrapper/"
            "actions/runs/2001/artifacts/3001"
        ),
    )
    assert "[BARK][DELIVERY_RECEIPT]" in comment
    assert "Delivery status: `DELIVERED`" in comment
    assert "Request initiated: `true`" in comment
    assert "HTTP status: `200`" in comment
    assert "actions/runs/2001" in comment
    assert "artifacts/3001" in comment
    assert "Artifact upload: `UPLOADED`" in comment
    assert "devflow-bark-delivery-receipt:devflow-root:" in comment
    assert "BARK_PUSH_URL" not in comment
    assert "device_key" not in comment


def test_failed_artifact_upload_comment_remains_fail_open() -> None:
    comment = render_receipt_comment(
        receipt=_receipt(),
        repository=REPOSITORY,
        artifact_upload_status="FAILED",
        artifact_id=None,
        artifact_url=None,
    )
    assert "unavailable (upload failed open)" in comment
    assert "Artifact upload: `FAILED`" in comment
    assert "Delivery status: `DELIVERED`" in comment


def test_uploaded_receipt_requires_exact_repository_run_and_artifact() -> None:
    bad_urls = (
        "https://example.com/artifacts/3001",
        "https://github.com/other/repo/actions/runs/2001/artifacts/3001",
        "https://github.com/tyxq428/ashare_f10_scrapper/actions/runs/999/artifacts/3001",
        "https://github.com/tyxq428/ashare_f10_scrapper/actions/runs/2001/artifacts/999",
    )
    for url in bad_urls:
        with pytest.raises(
            BarkDeliveryReceiptCommentError,
            match="artifact_url",
        ):
            render_receipt_comment(
                receipt=_receipt(),
                repository=REPOSITORY,
                artifact_upload_status="UPLOADED",
                artifact_id=3001,
                artifact_url=url,
            )


def test_failed_upload_rejects_artifact_metadata() -> None:
    with pytest.raises(BarkDeliveryReceiptCommentError, match="cannot include"):
        render_receipt_comment(
            receipt=_receipt(),
            repository=REPOSITORY,
            artifact_upload_status="FAILED",
            artifact_id=3001,
            artifact_url=(
                "https://github.com/tyxq428/ashare_f10_scrapper/"
                "actions/runs/2001/artifacts/3001"
            ),
        )


def test_receipt_comment_rejects_invalid_repository() -> None:
    with pytest.raises(BarkDeliveryReceiptCommentError, match="owner/name"):
        render_receipt_comment(
            receipt=_receipt(),
            repository="https://github.com/tyxq428/ashare_f10_scrapper",
            artifact_upload_status="FAILED",
            artifact_id=None,
            artifact_url=None,
        )
