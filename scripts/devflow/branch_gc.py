from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MANAGED_PREFIXES = ("task/codex-", "codex/", "recovery/", "runtime/")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


@dataclass(frozen=True)
class BranchDecision:
    branch: str
    action: str
    reason: str


def is_managed(branch: str) -> bool:
    return SAFE_BRANCH.fullmatch(branch) is not None and any(
        branch.startswith(prefix) for prefix in MANAGED_PREFIXES
    )


def plan_deletions(
    candidates: list[str],
    *,
    default_branch: str,
    active_branches: set[str],
    open_pr_heads: set[str],
    merge_verified: bool,
) -> list[BranchDecision]:
    decisions: list[BranchDecision] = []
    for branch in sorted(set(candidates)):
        if not is_managed(branch):
            decisions.append(BranchDecision(branch, "KEEP", "UNMANAGED_OR_INVALID_PREFIX"))
        elif branch == default_branch:
            decisions.append(BranchDecision(branch, "KEEP", "DEFAULT_BRANCH"))
        elif branch in active_branches:
            decisions.append(BranchDecision(branch, "KEEP", "ACTIVE_TASK_BRANCH"))
        elif branch in open_pr_heads:
            decisions.append(BranchDecision(branch, "KEEP", "OPEN_PULL_REQUEST"))
        elif not merge_verified:
            decisions.append(BranchDecision(branch, "KEEP", "MERGE_SHA_NOT_VERIFIED"))
        else:
            decisions.append(BranchDecision(branch, "DELETE", "COMPLETED_TASK_MANAGED_BRANCH"))
    return decisions


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _active_branches(path: Path) -> set[str]:
    value = _load_json(path)
    tasks = value.get("tasks", []) if isinstance(value, dict) else []
    return {
        item["branch"]
        for item in tasks
        if isinstance(item, dict)
        and item.get("status") != "DONE"
        and isinstance(item.get("branch"), str)
    }


def _open_pr_heads(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    value = _load_json(path)
    items = value if isinstance(value, list) else value.get("pull_requests", [])
    return {
        item["head"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("head"), str)
    }


def git_merge_verified(repo: Path, merge_sha: str, default_branch: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        return False
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            merge_sha,
            f"origin/{default_branch}",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--active-tasks", type=Path, required=True)
    parser.add_argument("--open-prs", type=Path)
    parser.add_argument("--merge-sha", required=True)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    decisions = plan_deletions(
        args.candidate,
        default_branch=args.default_branch,
        active_branches=_active_branches(args.active_tasks),
        open_pr_heads=_open_pr_heads(args.open_prs),
        merge_verified=git_merge_verified(args.repo.resolve(), args.merge_sha, args.default_branch),
    )
    payload = {
        "status": "PASS",
        "deletable": [item.branch for item in decisions if item.action == "DELETE"],
        "decisions": [asdict(item) for item in decisions],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
