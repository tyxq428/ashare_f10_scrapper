from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath


def _git_lines(repo_root: Path, args: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def normalize_path(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"unsafe path: {value}")
    return normalized.removeprefix("./")


def is_allowed(path: str, *, exact: set[str], prefixes: tuple[str, ...]) -> bool:
    if path in exact:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def collect_changed_paths(repo_root: Path, base: str | None) -> list[str]:
    values: set[str] = set()
    if base:
        values.update(_git_lines(repo_root, ["diff", "--name-only", f"{base}...HEAD"]))
    values.update(_git_lines(repo_root, ["diff", "--name-only"]))
    values.update(_git_lines(repo_root, ["diff", "--cached", "--name-only"]))
    values.update(_git_lines(repo_root, ["ls-files", "--others", "--exclude-standard"]))
    return sorted(normalize_path(item) for item in values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base")
    parser.add_argument("--allowed", action="append", default=[])
    parser.add_argument("--allow-prefix", action="append", default=[])
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    exact = {normalize_path(item) for item in args.allowed}
    prefixes = tuple(
        sorted({normalize_path(item).rstrip("/") for item in args.allow_prefix if item})
    )
    try:
        changed = collect_changed_paths(args.repo_root.resolve(), args.base)
    except (RuntimeError, ValueError) as exc:
        print(f"SCOPE_ERROR={exc}")
        return 1

    blocked = [
        path for path in changed if not is_allowed(path, exact=exact, prefixes=prefixes)
    ]
    summary = {
        "status": "PASS" if not blocked else "SECURITY_BLOCKED",
        "changed_files": changed,
        "blocked_files": blocked,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"SCOPE_STATUS={summary['status']}")
    print(f"SCOPE_CHANGED_COUNT={len(changed)}")
    print(f"SCOPE_BLOCKED_COUNT={len(blocked)}")
    for path in blocked:
        print(f"SCOPE_BLOCKED_PATH={path}")
    return 0 if not blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
