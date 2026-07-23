from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path


def load_task(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("task file must contain an object")
    allowed = value.get("allowed_files")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) for x in allowed):
        raise ValueError("allowed_files must be a non-empty string array")
    return value


def changed_files(base: str, head: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head],
        text=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def is_allowed(path: str, patterns: list[str]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def verify(paths: list[str], allowed: list[str]) -> list[str]:
    return sorted(path for path in paths if not is_allowed(path, allowed))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--head", default=None)
    parser.add_argument("--status", action="store_true", help="inspect working tree instead of a commit range")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    task = load_task(args.task_file)
    allowed = list(task["allowed_files"])
    if args.status:
        raw = subprocess.check_output(["git", "status", "--porcelain=v1"], text=True)
        paths = [line[3:] for line in raw.splitlines() if len(line) >= 4]
    else:
        head = args.head or "HEAD"
        paths = changed_files(args.base, head)
    violations = verify(paths, allowed)
    result = {
        "status": "PASS" if not violations else "FAIL",
        "changed_files": sorted(paths),
        "allowed_files": allowed,
        "violations": violations,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
