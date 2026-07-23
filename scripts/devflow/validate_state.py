from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from state_model import (
    TERMINAL_STATUSES,
    load_json_yaml,
    render_handoff,
    render_status,
    validate_state_shape,
)


def _git_is_ancestor(repo_root: Path, ancestor: str) -> bool:
    if not ancestor or not (repo_root / ".git").exists():
        return True
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=repo_root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def validate_task(
    repo_root: Path,
    task_entry: dict[str, Any],
    *,
    check_generated: bool,
    check_git: bool,
) -> list[str]:
    errors: list[str] = []
    task_id = str(task_entry.get("task_id") or "")
    state_rel = task_entry.get("state_file")
    if not isinstance(state_rel, str) or not state_rel:
        return [f"{task_id or '<unknown>'}: missing state_file"]

    state_path = repo_root / state_rel
    try:
        state = load_json_yaml(state_path)
    except ValueError as exc:
        return [str(exc)]

    prefix = f"{task_id}: "
    errors.extend(prefix + item for item in validate_state_shape(state))
    if state.get("task_id") != task_id:
        errors.append(prefix + "ACTIVE_TASKS task_id does not match state")
    if task_entry.get("branch") != state.get("working_branch"):
        errors.append(prefix + "ACTIVE_TASKS branch does not match state")
    if task_entry.get("status") != state.get("status"):
        errors.append(prefix + "ACTIVE_TASKS status does not match state")
    if task_entry.get("pull_request") != state.get("pull_request"):
        errors.append(prefix + "ACTIVE_TASKS pull_request does not match state")

    task_dir = state_path.parent
    for name in ("00_contract.md", "01_master_plan.md", "HANDOFF.md", "STATUS.md"):
        if not (task_dir / name).is_file():
            errors.append(prefix + f"missing required task document: {name}")

    current_stage = state.get("current_stage")
    if isinstance(current_stage, str) and not (task_dir / f"{current_stage}_plan.md").is_file():
        errors.append(prefix + f"missing current stage plan: {current_stage}_plan.md")

    for result_path in sorted(task_dir.glob("W??_result.md")):
        plan_path = result_path.with_name(result_path.name.replace("_result.md", "_plan.md"))
        if not plan_path.is_file():
            errors.append(prefix + f"{result_path.name} exists without {plan_path.name}")

    last_stage = state.get("last_completed_stage")
    if isinstance(last_stage, str) and not (task_dir / f"{last_stage}_result.md").is_file():
        errors.append(prefix + f"last completed stage lacks result: {last_stage}_result.md")

    if state.get("status") in TERMINAL_STATUSES and state.get("next_action") not in {"none", None}:
        errors.append(prefix + "terminal task must use next_action 'none'")

    if check_generated:
        status_path = task_dir / "STATUS.md"
        handoff_path = task_dir / "HANDOFF.md"
        if status_path.is_file() and status_path.read_text(encoding="utf-8") != render_status(state):
            errors.append(prefix + "STATUS.md is stale; run render_task_docs.py")
        if handoff_path.is_file() and handoff_path.read_text(encoding="utf-8") != render_handoff(state):
            errors.append(prefix + "HANDOFF.md is stale; run render_task_docs.py")

    if check_git and not _git_is_ancestor(repo_root, str(state.get("last_product_commit_sha") or "")):
        errors.append(prefix + "last_product_commit_sha is not an ancestor of HEAD")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--active-tasks",
        type=Path,
        default=Path("docs/implementation/ACTIVE_TASKS.yaml"),
    )
    parser.add_argument("--task-id")
    parser.add_argument("--check-generated", action="store_true")
    parser.add_argument("--skip-git", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    active_path = args.active_tasks
    if not active_path.is_absolute():
        active_path = repo_root / active_path
    try:
        active = load_json_yaml(active_path)
    except ValueError as exc:
        print(f"STATE_ERROR={exc}")
        return 1

    tasks = active.get("tasks")
    if not isinstance(tasks, list):
        print("STATE_ERROR=ACTIVE_TASKS.tasks must be a list")
        return 1

    errors: list[str] = []
    seen: set[str] = set()
    selected = 0
    for entry in tasks:
        if not isinstance(entry, dict):
            errors.append("ACTIVE_TASKS contains a non-object task")
            continue
        task_id = str(entry.get("task_id") or "")
        if task_id in seen:
            errors.append(f"duplicate active task_id: {task_id}")
        seen.add(task_id)
        if args.task_id and task_id != args.task_id:
            continue
        selected += 1
        errors.extend(
            validate_task(
                repo_root,
                entry,
                check_generated=args.check_generated,
                check_git=not args.skip_git,
            )
        )

    if args.task_id and selected == 0:
        errors.append(f"task not found: {args.task_id}")

    summary = {
        "status": "PASS" if not errors else "FAIL",
        "task_count": selected,
        "error_count": len(errors),
        "errors": errors,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"STATE_CONSISTENCY={summary['status']}")
    print(f"STATE_TASK_COUNT={selected}")
    print(f"STATE_ERROR_COUNT={len(errors)}")
    for error in errors:
        print(f"STATE_ERROR={error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
