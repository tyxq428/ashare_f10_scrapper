from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

DEVFLOW = Path(__file__).resolve().parents[1] / "scripts" / "devflow"
sys.path.insert(0, str(DEVFLOW))

from legacy_codex_branch_audit import (  # noqa: E402
    ACTION_PATH,
    DESCRIPTOR_PATH,
    MARKER_PATH,
    audit,
)


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def prepare_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    origin = tmp_path / "origin.git"
    run(["git", "init", "--bare", str(origin)], tmp_path)

    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.name", "test"], repo)
    run(["git", "config", "user.email", "test@example.invalid"], repo)
    run(["git", "remote", "add", "origin", str(origin)], repo)

    descriptor = repo / DESCRIPTOR_PATH
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text('{"task_id":"legacy"}\n', encoding="utf-8")
    action = repo / ACTION_PATH
    action.parent.mkdir(parents=True)
    action.write_text(
        "name: active\nruns:\n  using: composite\n  steps:\n"
        "    - uses: openai/codex-action@deadbeef\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("legacy\n", encoding="utf-8")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "legacy task"], repo)
    run(["git", "branch", "-M", "task/codex-legacy"], repo)
    run(["git", "push", "-u", "origin", "task/codex-legacy"], repo)

    canonical = tmp_path / "disabled-action.yml"
    canonical.write_text(
        "name: disabled\nruns:\n  using: composite\n  steps:\n"
        "    - shell: bash\n      run: echo CODEX_MODEL_INVOCATION=DISABLED\n",
        encoding="utf-8",
    )
    control_sha = "a" * 40
    return repo, canonical, control_sha


def test_execute_quarantines_legacy_task_branch(tmp_path: Path) -> None:
    repo, canonical, control_sha = prepare_repo(tmp_path)
    summary = audit(
        repo=repo,
        open_pr_heads=set(),
        execute=True,
        canonical_action=canonical,
        control_sha=control_sha,
    )
    assert summary.status == "PASS"
    assert summary.branch_count == 1
    assert summary.quarantined_count == 1
    snapshot = summary.branches[0]
    assert snapshot.status == "QUARANTINED"
    assert snapshot.descriptor_present is False
    assert snapshot.action_disabled is True
    assert snapshot.action_has_model_reference is False
    assert snapshot.marker_valid is True

    run(
        [
            "git",
            "fetch",
            "origin",
            "+refs/heads/task/codex-legacy:refs/remotes/origin/task/codex-legacy",
        ],
        repo,
    )
    missing = subprocess.run(
        [
            "git",
            "show",
            f"refs/remotes/origin/task/codex-legacy:{DESCRIPTOR_PATH}",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0
    marker = json.loads(
        run(
            [
                "git",
                "show",
                f"refs/remotes/origin/task/codex-legacy:{MARKER_PATH}",
            ],
            repo,
        )
    )
    assert marker["status"] == "QUARANTINED"
    assert marker["model_invocation"] is False


def test_open_pr_branch_is_never_modified(tmp_path: Path) -> None:
    repo, canonical, control_sha = prepare_repo(tmp_path)
    before = run(["git", "ls-remote", "origin", "refs/heads/task/codex-legacy"], repo)
    summary = audit(
        repo=repo,
        open_pr_heads={"task/codex-legacy"},
        execute=True,
        canonical_action=canonical,
        control_sha=control_sha,
    )
    after = run(["git", "ls-remote", "origin", "refs/heads/task/codex-legacy"], repo)
    assert summary.status == "FAIL"
    assert summary.blocked_open_pr_count == 1
    assert summary.quarantined_count == 0
    assert before == after


def test_empty_remote_branch_set_passes(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    run(["git", "init", "--bare", str(origin)], tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "remote", "add", "origin", str(origin)], repo)
    canonical = tmp_path / "disabled-action.yml"
    canonical.write_text(
        "name: disabled\n# CODEX_MODEL_INVOCATION=DISABLED\n",
        encoding="utf-8",
    )
    summary = audit(
        repo=repo,
        open_pr_heads=set(),
        execute=False,
        canonical_action=canonical,
        control_sha="b" * 40,
    )
    assert summary.status == "PASS"
    assert summary.branch_count == 0
