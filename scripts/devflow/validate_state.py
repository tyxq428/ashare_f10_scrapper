from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from state_model import (
    StateError,
    TaskState,
    load_json_yaml,
    required_task_files,
)


def git_is_ancestor(
    repo: Path,
    ancestor: str,
    head: str = "HEAD",
) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            ancestor,
            head,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def stage_number(stage: str) -> int | None:
    match = re.fullmatch(r"W(\d{2})", stage)
    return int(match.group(1)) if match else None


def branch_matches_state(
    current_branch: str,
    state: TaskState,
) -> bool:
    """Return whether checkout branch is valid for canonical state."""

    if not current_branch or state.status == "DONE":
        return True
    if current_branch == state.working_branch:
        return True
    number = stage_number(state.current_stage)
    return (
        current_branch == "main"
        and state.pull_request is not None
        and number is not None
        and number >= 5
    )


def validate_active_index(
    repo: Path,
    state: TaskState,
    state_path: Path,
) -> list[str]:
    errors: list[str] = []
    index_path = repo / "docs/implementation/ACTIVE_TASKS.yaml"
    try:
        index = load_json_yaml(index_path)
    except StateError as exc:
        return [str(exc)]
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        return ["ACTIVE_TASKS.tasks must be an array"]
    matches = [
        item
        for item in tasks
        if isinstance(item, dict)
        and item.get("task_id") == state.task_id
    ]
    if state.status == "DONE":
        if len(matches) > 1:
            errors.append(
                "completed task appears more than once in ACTIVE_TASKS"
            )
        return errors
    if len(matches) != 1:
        errors.append(
            "active task must appear exactly once in ACTIVE_TASKS"
        )
        return errors
    entry = matches[0]
    relative_state = state_path.relative_to(repo).as_posix()
    expected = {
        "status": state.status,
        "branch": state.working_branch,
        "current_stage": state.current_stage,
        "state_path": relative_state,
    }
    for key, value in expected.items():
        if entry.get(key) != value:
            errors.append(
                f"ACTIVE_TASKS.{key} does not match canonical state"
            )
    return errors


def validate(
    repo: Path,
    task_dir: Path,
    *,
    check_git: bool = True,
    check_checkout_branch: bool = True,
) -> dict[str, object]:
    state_path = task_dir / "task_state.yaml"
    errors: list[str] = []
    try:
        mapping = load_json_yaml(state_path)
        state = TaskState.from_mapping(mapping)
    except StateError as exc:
        return {
            "status": "FAIL",
            "task_dir": task_dir.relative_to(repo).as_posix(),
            "errors": [str(exc)],
        }

    for path in required_task_files(task_dir, state):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(
                "missing required file: "
                f"{path.relative_to(repo).as_posix()}"
            )

    errors.extend(
        validate_active_index(
            repo,
            state,
            state_path,
        )
    )

    if check_git:
        product_sha = mapping["last_product_commit_sha"]
        if not git_is_ancestor(repo, product_sha):
            errors.append(
                "last_product_commit_sha is not an ancestor of HEAD"
            )
        if check_checkout_branch:
            current_branch = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "branch",
                    "--show-current",
                ],
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if not branch_matches_state(current_branch, state):
                errors.append(
                    "working_branch mismatch: "
                    f"state={state.working_branch}, "
                    f"checkout={current_branch}"
                )

    return {
        "status": "PASS" if not errors else "FAIL",
        "task_id": state.task_id,
        "task_dir": task_dir.relative_to(repo).as_posix(),
        "schema_version": state.schema_version,
        "current_stage": state.current_stage,
        "errors": errors,
    }


def active_task_dirs(repo: Path) -> list[Path]:
    index_path = repo / "docs/implementation/ACTIVE_TASKS.yaml"
    index = load_json_yaml(index_path)
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        raise StateError("ACTIVE_TASKS.tasks must be an array")

    result: list[Path] = []
    seen: set[str] = set()
    for item in tasks:
        if not isinstance(item, dict):
            raise StateError(
                "ACTIVE_TASKS entries must be objects"
            )
        task_id = item.get("task_id")
        state_path = item.get("state_path")
        if (
            not isinstance(task_id, str)
            or not task_id.strip()
            or not isinstance(state_path, str)
            or not state_path.strip()
        ):
            raise StateError(
                "ACTIVE_TASKS entries require task_id and state_path"
            )
        if task_id in seen:
            raise StateError(
                f"duplicate task_id in ACTIVE_TASKS: {task_id}"
            )
        seen.add(task_id)
        resolved = (repo / state_path).resolve()
        try:
            resolved.relative_to(repo)
        except ValueError as exc:
            raise StateError(
                f"state_path escapes repository: {state_path}"
            ) from exc
        if resolved.name != "task_state.yaml":
            raise StateError(
                f"state_path must end with task_state.yaml: {state_path}"
            )
        result.append(resolved.parent)
    return result


def validate_all(
    repo: Path,
    *,
    check_git: bool = True,
    check_checkout_branch: bool = True,
) -> dict[str, object]:
    try:
        task_dirs = active_task_dirs(repo)
    except StateError as exc:
        return {
            "status": "FAIL",
            "tasks": [],
            "errors": [str(exc)],
        }

    results = [
        validate(
            repo,
            task_dir,
            check_git=check_git,
            check_checkout_branch=check_checkout_branch,
        )
        for task_dir in task_dirs
    ]
    errors: list[str] = []
    for result in results:
        if result["status"] == "PASS":
            continue
        task_id = result.get("task_id") or result.get("task_dir")
        for error in result.get("errors", []):
            errors.append(f"{task_id}: {error}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "task_count": len(results),
        "tasks": results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=Path(
            "docs/implementation/chatgpt-web-codex-devflow-v1"
        ),
    )
    parser.add_argument("--all-active", action="store_true")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-git", action="store_true")
    parser.add_argument(
        "--allow-checkout-branch",
        action="store_true",
        help=(
            "keep ancestry checks but skip checkout-branch matching "
            "for trusted PR merge refs"
        ),
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    if args.all_active:
        result = validate_all(
            repo,
            check_git=not args.no_git,
            check_checkout_branch=not args.allow_checkout_branch,
        )
    else:
        task_dir = (
            (repo / args.task_dir).resolve()
            if not args.task_dir.is_absolute()
            else args.task_dir
        )
        result = validate(
            repo,
            task_dir,
            check_git=not args.no_git,
            check_checkout_branch=not args.allow_checkout_branch,
        )

    text = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output.write_text(
            text + "\n",
            encoding="utf-8",
        )
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
