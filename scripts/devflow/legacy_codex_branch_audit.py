from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BRANCH_PREFIX = "task/codex-"
DESCRIPTOR_PATH = ".agent/current_task.yaml"
ACTION_PATH = ".github/actions/codex-thin-worker/action.yml"
MARKER_PATH = ".devflow/legacy-codex-rerun-quarantine.json"
DISABLED_MARKER = "CODEX_MODEL_INVOCATION=DISABLED"
FORBIDDEN_ACTION_MARKER = "openai/codex-action@"


class BranchAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class BranchSnapshot:
    branch: str
    remote_sha: str
    open_pull_request: bool
    descriptor_present: bool
    action_present: bool
    action_disabled: bool
    action_has_model_reference: bool
    marker_present: bool
    marker_valid: bool
    status: str


@dataclass(frozen=True)
class AuditSummary:
    status: str
    execute: bool
    branch_count: int
    compliant_count: int
    quarantined_count: int
    blocked_open_pr_count: int
    noncompliant_count: int
    branches: tuple[BranchSnapshot, ...]


def _run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
    )


def _validate_branch(branch: str) -> str:
    value = branch.strip()
    if not value.startswith(BRANCH_PREFIX):
        raise BranchAuditError(f"unmanaged branch: {value}")
    if value.startswith("/") or value.endswith("/") or ".." in value:
        raise BranchAuditError(f"invalid branch name: {value}")
    if any(character.isspace() for character in value):
        raise BranchAuditError(f"invalid branch whitespace: {value}")
    return value


def list_remote_task_branches(repo: Path) -> dict[str, str]:
    result = _run(
        [
            "git",
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{BRANCH_PREFIX}*",
        ],
        cwd=repo,
    )
    branches: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            sha, ref = line.split("\t", 1)
        except ValueError as exc:
            raise BranchAuditError(f"invalid ls-remote line: {line!r}") from exc
        branch = _validate_branch(ref.removeprefix("refs/heads/"))
        if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
            raise BranchAuditError(f"invalid remote SHA for {branch}")
        branches[branch] = sha
    return dict(sorted(branches.items()))


def load_open_pr_heads(path: Path | None) -> set[str]:
    if path is None:
        return set()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BranchAuditError(f"cannot load open PR heads: {path}") from exc
    if not isinstance(value, list):
        raise BranchAuditError("open PR heads root must be a list")
    heads: set[str] = set()
    for item in value:
        if isinstance(item, str):
            heads.add(item)
        elif isinstance(item, dict) and isinstance(item.get("headRefName"), str):
            heads.add(item["headRefName"])
        else:
            raise BranchAuditError("open PR head entries must be strings or objects")
    return heads


def _fetch_branch(repo: Path, branch: str) -> str:
    branch = _validate_branch(branch)
    remote_ref = f"refs/remotes/origin/{branch}"
    _run(
        [
            "git",
            "fetch",
            "--no-tags",
            "origin",
            f"+refs/heads/{branch}:{remote_ref}",
        ],
        cwd=repo,
    )
    return remote_ref


def _read_ref_file(repo: Path, ref: str, path: str) -> str | None:
    result = _run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _valid_marker(text: str | None, branch: str) -> bool:
    if text is None:
        return False
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 1
        and value.get("branch") == branch
        and value.get("status") == "QUARANTINED"
        and value.get("model_invocation") is False
        and value.get("historical_workflow_rerun") == "BLOCKED_BEFORE_SECRET_JOB"
    )


def inspect_branch(
    repo: Path,
    branch: str,
    remote_sha: str,
    open_pr_heads: set[str],
) -> BranchSnapshot:
    remote_ref = _fetch_branch(repo, branch)
    descriptor = _read_ref_file(repo, remote_ref, DESCRIPTOR_PATH)
    action = _read_ref_file(repo, remote_ref, ACTION_PATH)
    marker = _read_ref_file(repo, remote_ref, MARKER_PATH)
    action_disabled = action is not None and DISABLED_MARKER in action
    action_has_model_reference = action is not None and FORBIDDEN_ACTION_MARKER in action
    marker_valid = _valid_marker(marker, branch)
    open_pr = branch in open_pr_heads
    compliant = (
        not open_pr
        and descriptor is None
        and action_disabled
        and not action_has_model_reference
        and marker_valid
    )
    if open_pr:
        status = "BLOCKED_OPEN_PR"
    elif compliant:
        status = "QUARANTINED"
    else:
        status = "NEEDS_QUARANTINE"
    return BranchSnapshot(
        branch=branch,
        remote_sha=remote_sha,
        open_pull_request=open_pr,
        descriptor_present=descriptor is not None,
        action_present=action is not None,
        action_disabled=action_disabled,
        action_has_model_reference=action_has_model_reference,
        marker_present=marker is not None,
        marker_valid=marker_valid,
        status=status,
    )


def _write_marker(worktree: Path, branch: str, control_sha: str) -> None:
    path = worktree / MARKER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    value: dict[str, Any] = {
        "schema_version": 1,
        "branch": branch,
        "status": "QUARANTINED",
        "reason": "Prevent historical Codex Task workflow re-runs from reaching a secret-bearing model job.",
        "model_invocation": False,
        "historical_workflow_rerun": "BLOCKED_BEFORE_SECRET_JOB",
        "control_sha": control_sha,
        "quarantined_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quarantine_branch(
    repo: Path,
    branch: str,
    *,
    canonical_action: Path,
    control_sha: str,
) -> bool:
    branch = _validate_branch(branch)
    remote_ref = _fetch_branch(repo, branch)
    with tempfile.TemporaryDirectory(prefix="legacy-codex-quarantine-") as directory:
        worktree = Path(directory)
        _run(["git", "worktree", "add", "--detach", str(worktree), remote_ref], cwd=repo)
        try:
            descriptor = worktree / DESCRIPTOR_PATH
            if descriptor.exists():
                descriptor.unlink()
                parent = descriptor.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()

            action_path = worktree / ACTION_PATH
            action_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical_action, action_path)
            _write_marker(worktree, branch, control_sha)

            _run(["git", "add", "-A"], cwd=worktree)
            changed = _run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=worktree,
                check=False,
            ).returncode != 0
            if not changed:
                return False
            _run(["git", "config", "user.name", "github-actions[bot]"], cwd=worktree)
            _run(
                [
                    "git",
                    "config",
                    "user.email",
                    "41898282+github-actions[bot]@users.noreply.github.com",
                ],
                cwd=worktree,
            )
            _run(
                [
                    "git",
                    "commit",
                    "-m",
                    "Quarantine legacy Codex task branch from historical reruns",
                ],
                cwd=worktree,
            )
            _run(
                ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
                cwd=worktree,
            )
            return True
        finally:
            _run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=repo,
                check=False,
            )


def audit(
    *,
    repo: Path,
    open_pr_heads: set[str],
    execute: bool,
    canonical_action: Path,
    control_sha: str,
) -> AuditSummary:
    branches = list_remote_task_branches(repo)
    quarantined_count = 0
    initial: list[BranchSnapshot] = []
    for branch, sha in branches.items():
        snapshot = inspect_branch(repo, branch, sha, open_pr_heads)
        initial.append(snapshot)
        if execute and snapshot.status == "NEEDS_QUARANTINE":
            if quarantine_branch(
                repo,
                branch,
                canonical_action=canonical_action,
                control_sha=control_sha,
            ):
                quarantined_count += 1

    final: list[BranchSnapshot] = []
    refreshed = list_remote_task_branches(repo)
    for branch, sha in refreshed.items():
        final.append(inspect_branch(repo, branch, sha, open_pr_heads))

    blocked = sum(item.status == "BLOCKED_OPEN_PR" for item in final)
    compliant = sum(item.status == "QUARANTINED" for item in final)
    noncompliant = sum(item.status != "QUARANTINED" for item in final)
    return AuditSummary(
        status="PASS" if noncompliant == 0 else "FAIL",
        execute=execute,
        branch_count=len(final),
        compliant_count=compliant,
        quarantined_count=quarantined_count,
        blocked_open_pr_count=blocked,
        noncompliant_count=noncompliant,
        branches=tuple(final),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--open-pr-heads-json", type=Path)
    parser.add_argument(
        "--canonical-action",
        type=Path,
        default=Path(".github/actions/codex-thin-worker/action.yml"),
    )
    parser.add_argument("--control-sha", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    canonical_action = args.canonical_action.resolve()
    if not canonical_action.is_file():
        raise SystemExit("canonical disabled action is missing")
    action_text = canonical_action.read_text(encoding="utf-8")
    if DISABLED_MARKER not in action_text or FORBIDDEN_ACTION_MARKER in action_text:
        raise SystemExit("canonical action is not a safe disabled circuit breaker")

    summary = audit(
        repo=repo,
        open_pr_heads=load_open_pr_heads(args.open_pr_heads_json),
        execute=args.execute,
        canonical_action=canonical_action,
        control_sha=args.control_sha,
    )
    payload = asdict(summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if summary.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
