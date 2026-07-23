from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from state_model import StateError, TaskState, load_json_yaml, required_task_files


def git_is_ancestor(repo: Path, ancestor: str, head: str = "HEAD") -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, head],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def validate_active_index(repo: Path, state: TaskState, state_path: Path) -> list[str]:
    errors: list[str] = []
    index_path = repo / "docs/implementation/ACTIVE_TASKS.yaml"
    try:
        index = load_json_yaml(index_path)
    except StateError as exc:
        return [str(exc)]
    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        return ["ACTIVE_TASKS.tasks must be an array"]
    matches = [item for item in tasks if isinstance(item, dict) and item.get("task_id") == state.task_id]
    if state.status == "DONE":
        if len(matches) > 1:
            errors.append("completed task appears more than once in ACTIVE_TASKS")
        return errors
    if len(matches) != 1:
        errors.append("active task must appear exactly once in ACTIVE_TASKS")
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
            errors.append(f"ACTIVE_TASKS.{key} does not match canonical state")
    return errors


def validate(repo: Path, task_dir: Path, *, check_git: bool = True) -> dict[str, object]:
    state_path = task_dir / "task_state.yaml"
    errors: list[str] = []
    try:
        mapping = load_json_yaml(state_path)
        state = TaskState.from_mapping(mapping)
    except StateError as exc:
        return {"status": "FAIL", "errors": [str(exc)]}

    for path in required_task_files(task_dir, state):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing required file: {path.relative_to(repo).as_posix()}")

    errors.extend(validate_active_index(repo, state, state_path))

    if check_git:
        product_sha = mapping["last_product_commit_sha"]
        if not git_is_ancestor(repo, product_sha):
            errors.append("last_product_commit_sha is not an ancestor of HEAD")
        current_branch = subprocess.run(
            ["git", "-C", str(repo), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if current_branch and current_branch != state.working_branch and state.status != "DONE":
            errors.append(
                f"working_branch mismatch: state={state.working_branch}, checkout={current_branch}"
            )

    return {
        "status": "PASS" if not errors else "FAIL",
        "task_id": state.task_id,
        "current_stage": state.current_stage,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=Path("docs/implementation/chatgpt-web-codex-devflow-v1"),
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-git", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    task_dir = (repo / args.task_dir).resolve() if not args.task_dir.is_absolute() else args.task_dir
    result = validate(repo, task_dir, check_git=not args.no_git)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
