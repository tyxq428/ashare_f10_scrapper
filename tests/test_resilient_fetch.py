from __future__ import annotations

import json
from pathlib import Path

from scripts.run_resilient_fetch import classify_failure


def test_transient_http_502_is_retryable(tmp_path: Path) -> None:
    retryable, reason, failed_groups = classify_failure(
        "httpx.HTTPStatusError: HTTP 502 Bad Gateway",
        tmp_path,
        1,
    )
    assert retryable is True
    assert "retryable" in reason
    assert failed_groups is None


def test_permission_blocked_is_not_retried(tmp_path: Path) -> None:
    retryable, reason, _ = classify_failure(
        "PERMISSION_BLOCKED: CAPTCHA_REQUIRED",
        tmp_path,
        1,
    )
    assert retryable is False
    assert "non-retryable" in reason


def test_failed_group_metadata_is_retryable(tmp_path: Path) -> None:
    (tmp_path / "combined.json").write_text(
        json.dumps({"metadata": {"failed_group_count": 2}}),
        encoding="utf-8",
    )
    retryable, reason, failed_groups = classify_failure("unknown execution error", tmp_path, 1)
    assert retryable is True
    assert failed_groups == 2
    assert "2 F10 request groups" in reason


def test_unclassified_configuration_error_stops(tmp_path: Path) -> None:
    retryable, reason, _ = classify_failure("unknown option --bad", tmp_path, 2)
    assert retryable is False
    assert "non-retryable" in reason
