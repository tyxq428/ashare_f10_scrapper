from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

MAX_LOG_CHARS = 12_000
SENSITIVE_ENV_NAMES = (
    "AGENT_RESPONSES_ENDPOINT",
    "AGENT_API_KEY",
    "AGENT_MODEL",
)


def sensitive_values() -> set[str]:
    values: set[str] = set()
    for name in SENSITIVE_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if len(value) >= 3:
            values.add(value)
        if name == "AGENT_RESPONSES_ENDPOINT" and value:
            parsed = urlsplit(value)
            if parsed.netloc:
                values.add(parsed.netloc)
            if parsed.hostname:
                values.add(parsed.hostname)
    return values


def scrub(text: str) -> str:
    result = text
    for value in sorted(sensitive_values(), key=len, reverse=True):
        result = result.replace(value, "***")
    return result


def bounded_log_tail(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return scrub(path.read_text(encoding="utf-8", errors="replace")[-MAX_LOG_CHARS:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--failure-class", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--checkpoint", action="append", default=[])
    parser.add_argument("--minimum-action", default="Review the failure bundle.")
    parser.add_argument("--recovery-entry", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("devflow-artifacts/failure"))
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    log_tail = bounded_log_tail(args.log)
    data = {
        "task_id": args.task_id,
        "stage": args.stage,
        "failure_class": args.failure_class,
        "command": scrub(args.command),
        "exit_code": args.exit_code,
        "attempts": args.attempts,
        "changed_files": sorted(set(args.changed_file)),
        "successful_checkpoints": args.checkpoint,
        "minimum_action": scrub(args.minimum_action),
        "recovery_entry": args.recovery_entry,
        "log_tail": log_tail,
        "secret_values_included": False,
    }
    (output_dir / "failure.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = (
        "# Failure bundle\n\n"
        f"- Task / stage: `{args.task_id}` / `{args.stage}`\n"
        f"- Failure class: `{args.failure_class}`\n"
        f"- Failed command: `{scrub(args.command)}`\n"
        f"- Exit code: `{args.exit_code}`\n"
        f"- Attempts: `{args.attempts}`\n"
        f"- Changed files: `{', '.join(sorted(set(args.changed_file))) or 'none'}`\n"
        f"- Successful checkpoints: `{', '.join(args.checkpoint) or 'none'}`\n"
        f"- Minimum human action: {scrub(args.minimum_action)}\n"
        f"- Recovery entry: `{args.recovery_entry}`\n\n"
        "## Bounded relevant log tail\n\n"
        "```text\n"
        f"{log_tail}\n"
        "```\n"
    )
    (output_dir / "FAILURE_BUNDLE.md").write_text(markdown, encoding="utf-8")
    print("FAILURE_BUNDLE=CREATED")
    print(f"FAILURE_CLASS={args.failure_class}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
