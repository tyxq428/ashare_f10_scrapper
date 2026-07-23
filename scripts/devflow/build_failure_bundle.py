from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

MAX_LOG_CHARS = 16000


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bounded_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= MAX_LOG_CHARS:
        return text
    head = text[:4000]
    tail = text[-12000:]
    return f"{head}\n\n... LOG TRUNCATED ...\n\n{tail}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--command", default="")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--changed-files", type=Path)
    parser.add_argument("--recovery", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    files: list[str] = []
    if args.changed_files and args.changed_files.is_file():
        parsed = json.loads(args.changed_files.read_text(encoding="utf-8"))
        value = parsed.get("changed_files", []) if isinstance(parsed, dict) else []
        files = [str(item) for item in value[:50]]

    bundle = {
        "schema_version": 1,
        "task_id": args.task_id,
        "stage": args.stage,
        "classification": args.classification,
        "command": args.command,
        "exit_code": args.exit_code,
        "changed_files": files,
        "bounded_log": bounded_text(args.log),
        "recovery_entry": args.recovery,
        "created_at_utc": utc_now(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FAILURE_BUNDLE_WRITTEN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
