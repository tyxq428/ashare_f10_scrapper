from __future__ import annotations

import json
import sys
from pathlib import Path
from runpy import run_path

fetch_script = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "run_resilient_fetch.py"))
command_script = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "run_resilient_command.py"))
classify_failure = fetch_script["classify_failure"]
run_streamed = command_script["run_streamed"]
retryable_command_error = command_script["RETRYABLE"]


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


def test_official_source_network_unreachable_is_retryable() -> None:
    message = (
        "OfficialSourceError: SSE公告查询失败: HTTPSConnectionPool(host='query.sse.com.cn', "
        "port=443): Max retries exceeded (Caused by NewConnectionError: "
        "Failed to establish a new connection: [Errno 101] Network is unreachable)"
    )
    assert retryable_command_error.search(message)


def test_non_network_official_source_error_is_not_retryable() -> None:
    assert retryable_command_error.search("OfficialSourceError: unsupported market mapping") is None


def test_resilient_command_streams_heartbeats(capsys) -> None:
    return_code, output = run_streamed(
        [
            sys.executable,
            "-c",
            "import time; print('begin', flush=True); time.sleep(1.3); print('end', flush=True)",
        ],
        heartbeat_seconds=1,
    )
    captured = capsys.readouterr().out
    assert return_code == 0
    assert "begin" in output and "end" in output
    assert "[resilient-command-monitor]" in captured
