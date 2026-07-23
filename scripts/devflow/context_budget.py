from __future__ import annotations

import argparse
import glob
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from task_descriptor import TaskDescriptor, load_task_descriptor


@dataclass(frozen=True)
class ContextBudgetResult:
    status: str
    task_bytes: int
    declared_allowed_files: int
    existing_files: tuple[str, ...]
    missing_or_new_paths: tuple[str, ...]
    total_existing_file_bytes: int
    largest_file_bytes: int
    violations: tuple[str, ...]


def _matches(repo: Path, pattern: str) -> list[Path]:
    path = repo / pattern
    if not any(token in pattern for token in ("*", "?", "[")):
        return [path] if path.is_file() else []
    return sorted(
        candidate
        for raw in glob.glob(str(path), recursive=True)
        if (candidate := Path(raw)).is_file()
    )


def inspect_context(repo: Path, task_file: Path, task: TaskDescriptor) -> ContextBudgetResult:
    budget = task.context_budget
    violations: list[str] = []
    task_bytes = task_file.stat().st_size
    if task_bytes > budget.max_task_bytes:
        violations.append("TASK_DESCRIPTOR_TOO_LARGE")
    if len(task.allowed_files) > budget.max_allowed_files:
        violations.append("TOO_MANY_ALLOWED_FILES")
    if budget.include_chat_history:
        violations.append("CHAT_HISTORY_FORBIDDEN")
    if budget.include_full_sop:
        violations.append("FULL_SOP_FORBIDDEN")

    existing: dict[str, Path] = {}
    missing: list[str] = []
    for pattern in task.allowed_files:
        matches = _matches(repo, pattern)
        if not matches:
            missing.append(pattern)
            continue
        for path in matches:
            relative = path.resolve().relative_to(repo.resolve()).as_posix()
            existing[relative] = path

    total = 0
    largest = 0
    for relative, path in sorted(existing.items()):
        size = path.stat().st_size
        total += size
        largest = max(largest, size)
        if size > budget.max_single_file_bytes:
            violations.append(f"SINGLE_FILE_TOO_LARGE:{relative}")
    if total > budget.max_total_allowed_file_bytes:
        violations.append("TOTAL_ALLOWED_FILES_TOO_LARGE")

    return ContextBudgetResult(
        status="PASS" if not violations else "FAIL",
        task_bytes=task_bytes,
        declared_allowed_files=len(task.allowed_files),
        existing_files=tuple(sorted(existing)),
        missing_or_new_paths=tuple(sorted(missing)),
        total_existing_file_bytes=total,
        largest_file_bytes=largest,
        violations=tuple(violations),
    )


def result_payload(result: ContextBudgetResult, task: TaskDescriptor) -> dict[str, Any]:
    payload = asdict(result)
    payload["budget"] = asdict(task.context_budget)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    task_file = args.task_file.resolve()
    _raw, task = load_task_descriptor(task_file)
    result = inspect_context(repo, task_file, task)
    payload = result_payload(result, task)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
