from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from gate_profiles import get_gate_profile


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--output", type=Path, default=Path("devflow-gate-result.json"))
    args = parser.parse_args()

    commands = get_gate_profile(args.profile)
    results: list[dict[str, object]] = []
    overall = 0
    for command in commands:
        started = time.monotonic()
        print(f"[gate:{args.profile}] running: {' '.join(command)}", flush=True)
        process = subprocess.run(command, check=False, text=True)
        elapsed = round(time.monotonic() - started, 3)
        results.append(
            {
                "command": command,
                "return_code": process.returncode,
                "elapsed_seconds": elapsed,
            }
        )
        if process.returncode != 0:
            overall = process.returncode or 1
            break

    summary = {
        "profile": args.profile,
        "status": "PASS" if overall == 0 else "FAIL",
        "commands": results,
        "completed_at_utc": utc_now(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"GATE_PROFILE_STATUS={summary['status']}")
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
