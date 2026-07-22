from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

RETRYABLE = re.compile(
    r"HTTP\s+(?:408|425|429|500|502|503|504)\b|"
    r"(?:Connect|Read|Write)?Timeout|timed?\s*out|"
    r"connection\s+(?:reset|aborted|refused|closed)|"
    r"remote\s+disconnected|server\s+disconnected|"
    r"temporary\s+failure|name\s+resolution|TLS|SSL",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_streamed(command: Sequence[str], *, heartbeat_seconds: int = 20) -> tuple[int, str]:
    """Run one command with live output and fixed heartbeats during quiet periods."""

    print(f"[resilient-command] command: {subprocess.list2cmdline(list(command))}", flush=True)
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    lines: list[str] = []
    lock = threading.Lock()
    last_output = time.monotonic()

    def reader() -> None:
        nonlocal last_output
        for line in process.stdout:
            with lock:
                lines.append(line.rstrip("\n"))
                last_output = time.monotonic()
            print(line, end="", flush=True)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    last_heartbeat = time.monotonic()
    while process.poll() is None:
        time.sleep(0.5)
        now = time.monotonic()
        if heartbeat_seconds > 0 and now - last_heartbeat >= heartbeat_seconds:
            with lock:
                quiet_seconds = int(now - last_output)
                line_count = len(lines)
            print(
                f"[resilient-command-monitor] {utc_now()} process alive; "
                f"quiet={quiet_seconds}s; output_lines={line_count}",
                flush=True,
            )
            last_heartbeat = now
    thread.join(timeout=10)
    return int(process.returncode or 0), "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finite retry wrapper for one external command")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=int, default=10)
    parser.add_argument("--heartbeat-seconds", type=int, default=20)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    for attempt in range(1, max(1, args.max_attempts) + 1):
        print(f"[resilient-command] attempt {attempt}", flush=True)
        return_code, output = run_streamed(
            command,
            heartbeat_seconds=max(0, args.heartbeat_seconds),
        )
        retryable = bool(RETRYABLE.search(output))
        output_log = args.report.parent / f"{args.report.stem}.attempt-{attempt}.log"
        output_log.write_text(output, encoding="utf-8")
        attempts.append(
            {
                "attempt": attempt,
                "return_code": return_code,
                "retryable": retryable,
                "output_log": str(output_log),
                "output_lines": len(output.splitlines()),
                "output_tail": output[-12000:],
                "completed_at_utc": utc_now(),
            }
        )
        args.report.write_text(
            json.dumps(
                {
                    "status": "PASS" if return_code == 0 else "RETRYING" if retryable else "FAILED",
                    "command": command,
                    "attempts": attempts,
                    "updated_at_utc": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if return_code == 0:
            return 0
        if not retryable or attempt >= args.max_attempts:
            return return_code or 1
        delay = max(0, args.backoff_seconds) * (2 ** (attempt - 1))
        print(f"[resilient-command] retry in {delay}s", flush=True)
        time.sleep(delay)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
