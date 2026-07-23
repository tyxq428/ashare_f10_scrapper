from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Sequence

PROFILES: dict[str, tuple[tuple[str, ...], ...]] = {
    "devflow-targeted": (
        ("python", "-m", "compileall", "-q", "scripts/devflow"),
        ("ruff", "check", "scripts/devflow", "tests/test_devflow.py"),
        ("pytest", "-q", "tests/test_devflow.py"),
    ),
    "resilient-command-targeted": (
        (
            "ruff",
            "check",
            "scripts/run_resilient_command.py",
            "tests/test_resilient_fetch.py",
        ),
        ("pytest", "-q", "tests/test_resilient_fetch.py"),
    ),
    "state-consistency": (
        (
            "python",
            "scripts/devflow/validate_state.py",
            "--check-generated",
            "--json-output",
            "devflow-artifacts/state-consistency.json",
        ),
    ),
}


def get_profile_commands(name: str) -> tuple[tuple[str, ...], ...]:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown gate profile: {name}") from exc


def run_command(
    command: Sequence[str], *, repo_root: Path, tail_limit: int = 120
) -> dict[str, object]:
    started = time.monotonic()
    process = subprocess.Popen(
        list(command),
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    tail: list[str] = []
    for line in process.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip("\n"))
        if len(tail) > tail_limit:
            tail.pop(0)
    return_code = int(process.wait())
    return {
        "command": list(command),
        "return_code": return_code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report", type=Path, default=Path("devflow-artifacts/gate-report.json")
    )
    args = parser.parse_args()

    try:
        commands = get_profile_commands(args.profile)
    except ValueError as exc:
        print(f"GATE_ERROR={exc}")
        return 2

    results: list[dict[str, object]] = []
    status = "PASS"
    for command in commands:
        result = run_command(command, repo_root=args.repo_root.resolve())
        results.append(result)
        if result["return_code"] != 0:
            status = "FAIL"
            break

    report = {"profile": args.profile, "status": status, "commands": results}
    report_path = args.report
    if not report_path.is_absolute():
        report_path = args.repo_root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"GATE_PROFILE={args.profile}")
    print(f"GATE_STATUS={status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
