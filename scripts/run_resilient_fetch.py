from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

RETRYABLE_PATTERNS = (
    r"HTTP\s+(?:408|425|429|500|502|503|504)\b",
    r"(?:Connect|Read|Write)?Timeout",
    r"timed?\s*out",
    r"connection\s+(?:reset|aborted|refused|closed)",
    r"temporary\s+failure",
    r"remote\s+disconnected",
    r"server\s+disconnected",
    r"name\s+resolution",
    r"TLS|SSL",
)
NON_RETRYABLE_PATTERNS = (
    r"unknown\s+option",
    r"no\s+such\s+command",
    r"schema_validation_error",
    r"permission_blocked",
    r"captcha_required",
    r"login_required",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class AttemptResult:
    attempt: int
    started_at_utc: str
    completed_at_utc: str
    return_code: int
    validation_return_code: int | None
    retryable: bool
    reason: str
    output_lines: int
    failed_group_count: int | None


def _failed_group_count(output_dir: Path) -> int | None:
    combined = output_dir / "combined.json"
    if combined.exists():
        try:
            payload = json.loads(combined.read_text(encoding="utf-8"))
            return int(payload.get("metadata", {}).get("failed_group_count", 0))
        except Exception:  # noqa: BLE001
            return None
    group_dir = output_dir / "groups"
    if not group_dir.exists():
        return None
    failed = 0
    seen = 0
    for path in group_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        seen += 1
        if not payload.get("success"):
            failed += 1
    return failed if seen else None


def classify_failure(text: str, output_dir: Path, return_code: int) -> tuple[bool, str, int | None]:
    failed_groups = _failed_group_count(output_dir)
    compact = text.lower()
    for pattern in NON_RETRYABLE_PATTERNS:
        if re.search(pattern, compact, re.IGNORECASE):
            return False, f"non-retryable pattern: {pattern}", failed_groups
    for pattern in RETRYABLE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"retryable network pattern: {pattern}", failed_groups
    if failed_groups and failed_groups > 0:
        return True, f"{failed_groups} F10 request groups failed", failed_groups
    if return_code in {124, 137, 143}:
        return True, f"retryable process exit code {return_code}", failed_groups
    return False, f"unclassified exit code {return_code}", failed_groups


def _directory_snapshot(output_dir: Path) -> str:
    groups = len(list((output_dir / "groups").glob("*.json"))) if (output_dir / "groups").exists() else 0
    raw = len(list((output_dir / "raw").glob("*.json.gz"))) if (output_dir / "raw").exists() else 0
    try:
        size = sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file())
    except OSError:
        size = 0
    return f"groups={groups}, raw={raw}, size={size / 1024 / 1024:.1f}MiB"


def run_streamed(command: Sequence[str], *, heartbeat_seconds: int, output_dir: Path) -> tuple[int, list[str]]:
    print("[resilient] command:", subprocess.list2cmdline(list(command)), flush=True)
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
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
        time.sleep(1)
        now = time.monotonic()
        if heartbeat_seconds > 0 and now - last_heartbeat >= heartbeat_seconds:
            with lock:
                quiet = int(now - last_output)
            print(
                f"[resilient-monitor] {utc_now()} process alive; quiet={quiet}s; "
                f"{_directory_snapshot(output_dir)}",
                flush=True,
            )
            last_heartbeat = now
    thread.join(timeout=10)
    return int(process.returncode or 0), lines


def run_simple(command: Sequence[str]) -> int:
    print("[resilient] validation:", subprocess.list2cmdline(list(command)), flush=True)
    return subprocess.run(list(command), check=False).returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run ashare-f10 fetch with finite retry and heartbeat monitoring")
    result.add_argument("stock_code")
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--workers", type=int, default=4)
    result.add_argument("--force", action="store_true")
    result.add_argument("--include-raw-pack", action="store_true")
    result.add_argument("--raw-pack-packs", default="default")
    result.add_argument("--raw-pack-max-docs", type=int, default=200)
    result.add_argument("--max-attempts", type=int, default=3)
    result.add_argument("--backoff-seconds", type=int, default=10)
    result.add_argument("--heartbeat-seconds", type=int, default=20)
    result.add_argument("--report", type=Path)
    result.add_argument("--skip-validate", action="store_true")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.report or args.output / "resilient-fetch-report.json"
    attempts: list[AttemptResult] = []
    final_status = "FAILED"
    failure_reason = "not started"

    for attempt in range(1, max(1, args.max_attempts) + 1):
        started = utc_now()
        command = [
            "ashare-f10",
            "fetch",
            args.stock_code,
            "--output",
            str(args.output),
            "--workers",
            str(args.workers),
        ]
        if args.force and attempt == 1:
            command.append("--force")
        if args.include_raw_pack:
            command.extend(
                [
                    "--include-raw-pack",
                    "--raw-pack-packs",
                    args.raw_pack_packs,
                    "--raw-pack-max-docs",
                    str(args.raw_pack_max_docs),
                ]
            )
        return_code, lines = run_streamed(
            command,
            heartbeat_seconds=max(0, args.heartbeat_seconds),
            output_dir=args.output,
        )
        validation_code: int | None = None
        if return_code == 0 and not args.skip_validate:
            validation_code = run_simple(["ashare-f10", "validate", str(args.output)])
            if validation_code != 0:
                return_code = validation_code
                lines.append(f"validation failed with exit code {validation_code}")
        if return_code == 0:
            retryable, reason, failed_groups = False, "success", _failed_group_count(args.output)
            final_status = "PASS"
            failure_reason = ""
        else:
            retryable, reason, failed_groups = classify_failure("\n".join(lines), args.output, return_code)
            failure_reason = reason
        attempts.append(
            AttemptResult(
                attempt=attempt,
                started_at_utc=started,
                completed_at_utc=utc_now(),
                return_code=return_code,
                validation_return_code=validation_code,
                retryable=retryable,
                reason=reason,
                output_lines=len(lines),
                failed_group_count=failed_groups,
            )
        )
        payload = {
            "schema_version": "1.0.0",
            "status": final_status if final_status == "PASS" else "RETRYING" if retryable else "FAILED",
            "stock_code": args.stock_code,
            "output_dir": str(args.output.resolve()),
            "include_raw_pack": args.include_raw_pack,
            "attempts": [asdict(item) for item in attempts],
            "failure_reason": failure_reason,
            "updated_at_utc": utc_now(),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if final_status == "PASS":
            print(f"[resilient] PASS after {attempt} attempt(s)", flush=True)
            return 0
        if not retryable or attempt >= args.max_attempts:
            print(f"[resilient] STOP: {reason}", file=sys.stderr, flush=True)
            break
        delay = max(0, args.backoff_seconds) * (2 ** (attempt - 1))
        print(f"[resilient] retryable failure: {reason}; next attempt in {delay}s", flush=True)
        time.sleep(delay)

    final_payload = {
        "schema_version": "1.0.0",
        "status": "FAILED",
        "stock_code": args.stock_code,
        "output_dir": str(args.output.resolve()),
        "include_raw_pack": args.include_raw_pack,
        "attempts": [asdict(item) for item in attempts],
        "failure_reason": failure_reason,
        "updated_at_utc": utc_now(),
    }
    report_path.write_text(json.dumps(final_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
