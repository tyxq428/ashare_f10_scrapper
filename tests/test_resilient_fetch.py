from __future__ import annotations

import json
import sys
from pathlib import Path
from runpy import run_path

fetch_script = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "run_resilient_fetch.py"))
command_script = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "run_resilient_command.py"))
classify_failure = fetch_script["classify_failure"]
command_main = command_script["main"]
run_streamed = command_script["run_streamed"]
retryable_command_error = command_script["RETRYABLE"]


def run_resilient_command(monkeypatch, tmp_path: Path, results: list[tuple[int, str]]) -> tuple[int, list[dict]]:
    report = tmp_path / "report.json"
    reports: list[dict] = []
    original_write_text = Path.write_text

    def fake_run_streamed(command, *, heartbeat_seconds):
        return results.pop(0)

    def capture_write_text(path, data, **kwargs):
        written = original_write_text(path, data, **kwargs)
        if path == report:
            reports.append(json.loads(data))
        return written

    monkeypatch.setitem(command_main.__globals__, "run_streamed", fake_run_streamed)
    monkeypatch.setattr(Path, "write_text", capture_write_text)
    monkeypatch.setattr(command_main.__globals__["time"], "sleep", lambda _delay: None)
    return_code = command_main(
        ["--max-attempts", "2", "--backoff-seconds", "0", "--report", str(report), "--", "command"]
    )
    return return_code, reports


def test_resilient_command_persists_pass_on_success(monkeypatch, tmp_path: Path) -> None:
    return_code, reports = run_resilient_command(monkeypatch, tmp_path, [(0, "done")])

    assert return_code == 0
    assert [report["status"] for report in reports] == ["PASS"]


def test_resilient_command_persists_failed_for_non_retryable_failure(monkeypatch, tmp_path: Path) -> None:
    return_code, reports = run_resilient_command(monkeypatch, tmp_path, [(2, "invalid option")])

    assert return_code == 2
    assert [report["status"] for report in reports] == ["FAILED"]
    assert reports[-1]["attempts"][-1]["retryable"] is False


def test_resilient_command_persists_retrying_before_another_attempt(monkeypatch, tmp_path: Path) -> None:
    return_code, reports = run_resilient_command(monkeypatch, tmp_path, [(1, "HTTP 503"), (0, "done")])

    assert return_code == 0
    assert [report["status"] for report in reports] == ["RETRYING", "PASS"]


def test_resilient_command_persists_failed_when_retries_are_exhausted(monkeypatch, tmp_path: Path) -> None:
    return_code, reports = run_resilient_command(monkeypatch, tmp_path, [(1, "HTTP 503"), (1, "HTTP 503")])

    assert return_code == 1
    assert [report["status"] for report in reports] == ["RETRYING", "FAILED"]
    assert reports[-1]["attempts"][-1]["retryable"] is True


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
