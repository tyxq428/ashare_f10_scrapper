from __future__ import annotations

import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from branch_gc import is_managed, plan_deletions  # noqa: E402


def decisions_by_branch(**kwargs):
    return {item.branch: item for item in plan_deletions(**kwargs)}


def test_managed_prefixes_are_explicit() -> None:
    assert is_managed("task/codex-one")
    assert is_managed("codex/one")
    assert is_managed("recovery/one")
    assert is_managed("runtime/observer")
    assert not is_managed("feature/one")
    assert not is_managed("../main")


def test_completed_managed_branches_are_deletable_after_merge_verification() -> None:
    result = decisions_by_branch(
        candidates=["task/codex-one", "codex/one"],
        default_branch="main",
        active_branches=set(),
        open_pr_heads=set(),
        merge_verified=True,
    )
    assert result["task/codex-one"].action == "DELETE"
    assert result["codex/one"].action == "DELETE"


def test_active_or_open_pr_branches_are_preserved() -> None:
    result = decisions_by_branch(
        candidates=["task/codex-active", "codex/open"],
        default_branch="main",
        active_branches={"task/codex-active"},
        open_pr_heads={"codex/open"},
        merge_verified=True,
    )
    assert result["task/codex-active"].reason == "ACTIVE_TASK_BRANCH"
    assert result["codex/open"].reason == "OPEN_PULL_REQUEST"


def test_unverified_merge_preserves_all_candidates() -> None:
    result = decisions_by_branch(
        candidates=["task/codex-one"],
        default_branch="main",
        active_branches=set(),
        open_pr_heads=set(),
        merge_verified=False,
    )
    assert result["task/codex-one"].action == "KEEP"
    assert result["task/codex-one"].reason == "MERGE_SHA_NOT_VERIFIED"


def test_unmanaged_branch_is_never_deleted() -> None:
    result = decisions_by_branch(
        candidates=["feature/important"],
        default_branch="main",
        active_branches=set(),
        open_pr_heads=set(),
        merge_verified=True,
    )
    assert result["feature/important"].action == "KEEP"
    assert result["feature/important"].reason == "UNMANAGED_OR_INVALID_PREFIX"


def test_duplicate_candidates_are_idempotent() -> None:
    decisions = plan_deletions(
        ["codex/one", "codex/one"],
        default_branch="main",
        active_branches=set(),
        open_pr_heads=set(),
        merge_verified=True,
    )
    assert len(decisions) == 1
