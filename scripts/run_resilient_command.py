from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

RETRYABLE = re.compile(
    r"HTTP\s+(?:408|425|429|500|502|503|504)\b|timeout|connection\s+(?:reset|aborted|refused)|temporary failure",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finite retry wrapper for one external command")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=int, default=10)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    attempts: list[dict] = []
    for attempt in range(1, max(1, args.max_attempts) + 1):
        print(f"[resilient-command] attempt {attempt}: {subprocess.list2cmdline(command)}", flush=True)
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(completed.stdout, end="", flush=True)
        retryable = bool(RETRYABLE.search(completed.stdout or ""))
        attempts.append(
            {
                "attempt": attempt,
                "return_code": completed.returncode,
                "retryable": retryable,
                "completed_at_utc": utc_now(),
            }
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "status": "PASS" if completed.returncode == 0 else "RETRYING" if retryable else "FAILED",
                    "command": command,
                    "attempts": attempts,
                    "updated_at_utc": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if completed.returncode == 0:
            return 0
        if not retryable or attempt >= args.max_attempts:
            return completed.returncode or 1
        delay = max(0, args.backoff_seconds) * (2 ** (attempt - 1))
        print(f"[resilient-command] retry in {delay}s", flush=True)
        time.sleep(delay)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
