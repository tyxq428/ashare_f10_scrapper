from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "origin/feature/devflow-operational-optimization-v2"
MAIN_SHA = "fb895fd372007f41f611b40b4cb0eb57476a6b32"
CLEAN_BRANCH = "feature/devflow-operational-optimization-v2-clean"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")


run("git", "fetch", "--no-tags", "origin", "feature/devflow-operational-optimization-v2")

copy_paths = [
    "AGENTS.md",
    "docs/implementation/ACTIVE_TASKS.yaml",
    "docs/implementation/devflow-operational-optimization-v2",
    "docs/process/README.md",
    "docs/process/policies/cache-and-impact-gates.md",
    "docs/process/policies/gates-and-merge.md",
    "docs/process/policies/monitoring-and-recovery.md",
    "docs/process/policies/state-and-documentation.md",
    "docs/process/runbooks/branch-garbage-collection.md",
    "docs/process/runbooks/run-codex-thin-worker.md",
    "docs/process/runbooks/upgrade-compatibility.md",
    "docs/process/templates/codex_task.template.yaml",
    "docs/process/templates/task_state.template.yaml",
    ".github/workflows/devflow-branch-gc.yml",
    ".github/workflows/devflow-infrastructure-post-merge.yml",
    ".github/workflows/devflow-state-consistency.yml",
    ".github/workflows/devflow-upgrade-compatibility.yml",
    ".github/workflows/test.yml",
    ".github/workflows/e2e-688521.yml",
    "scripts/devflow/append_engineering_lessons.py",
    "scripts/devflow/branch_gc.py",
    "scripts/devflow/change_impact.py",
    "scripts/devflow/context_budget.py",
    "scripts/devflow/gate_profiles.py",
    "scripts/devflow/recovery_task.py",
    "scripts/devflow/render_task_docs.py",
    "scripts/devflow/state_model.py",
    "scripts/devflow/task_descriptor.py",
    "scripts/devflow/upgrade_compatibility.py",
    "scripts/devflow/validate_docs.py",
    "scripts/devflow/validate_state.py",
    "tests/fixtures/devflow",
    "tests/test_devflow_branch_gc.py",
    "tests/test_devflow_change_impact.py",
    "tests/test_devflow_context_budget.py",
    "tests/test_devflow_state_v2.py",
    "tests/test_devflow_upgrade_compatibility.py",
    "tests/test_devflow_validate_docs.py",
    "tests/test_devflow_codex_environment.py",
]
run("git", "checkout", SOURCE, "--", *copy_paths)

# Preserve the reviewed main-branch Codex freeze and recovery circuit breaker.
for duplicate in (
    ".github/actions/codex-thin-worker-v2/action.yml",
    ".github/workflows/temporary-patch-codex-v2-reference.yml",
    "scripts/devflow/recovery_policy_v2.py",
    "scripts/devflow/validate_workflows_v2.py",
):
    target = ROOT / duplicate
    if target.exists():
        if target.is_file():
            target.unlink()

# Do not let Path normalization erase the leading dot in `.github`.
path = ROOT / "scripts/devflow/change_impact.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    """    normalized = sorted(\n        {\n            path.strip().lstrip(\"./\")\n            for path in paths\n            if path.strip()\n        }\n    )\n""",
    """    normalized_values: set[str] = set()\n    for raw_path in paths:\n        value = raw_path.strip()\n        while value.startswith(\"./\"):\n            value = value[2:]\n        if value:\n            normalized_values.add(value)\n    normalized = sorted(normalized_values)\n""",
)
path.write_text(text, encoding="utf-8")

# Add a regression for the `.github` normalization defect.
path = ROOT / "tests/test_devflow_change_impact.py"
text = path.read_text(encoding="utf-8")
if "test_github_leading_dot_is_preserved" not in text:
    text += """\n\ndef test_github_leading_dot_is_preserved() -> None:\n    result = classify_paths([\".github/workflows/test.yml\"])\n    assert result.impact == \"devflow_only\"\n    assert result.changed_files == (\".github/workflows/test.yml\",)\n    assert \"devflow:.github/workflows/test.yml\" in result.reasons\n"""
path.write_text(text, encoding="utf-8")

# Adapt Codex environment tests to the repository-wide disabled policy.
path = ROOT / "tests/test_devflow_codex_environment.py"
text = path.read_text(encoding="utf-8")
start = text.index("def test_reusable_unit_allows_only_trusted_bot_and_uses_xhigh() -> None:\n")
end = text.index("\n\ndef test_new_template_is_schema_v2_xhigh", start)
replacement = '''def test_reusable_unit_is_frozen_before_any_model_call() -> None:\n    action = REPO / ".github/actions/codex-thin-worker/action.yml"\n    text = action.read_text(encoding="utf-8")\n    policy = json.loads((REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8"))\n    assert policy["mode"] == "disabled"\n    assert "CODEX_POLICY_DISABLED" in text\n    assert "CODEX_MODEL_INVOCATION=DISABLED" in text\n    assert "openai/codex-action@" not in text\n    assert "secrets." not in text\n    assert validate_file(action) == []\n'''
text = text[:start] + replacement + text[end:]
start = text.index("def test_auto_recovery_generates_schema_v2_xhigh_tasks() -> None:\n")
end = text.index("\n\ndef test_context_budget_precedes_private_runtime", start)
replacement = '''def test_auto_recovery_does_not_dispatch_or_retry_codex_while_frozen() -> None:\n    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"\n    text = workflow.read_text(encoding="utf-8")\n    assert "RETRY_CODEX" not in text\n    assert "Repair the deterministic devflow state or validation failure" not in text\n    assert validate_file(workflow) == []\n'''
text = text[:start] + replacement + text[end:]
text = text.replace(
    '        "value: ${{ steps.run-codex.outputs.final-message }}"\n        in action_text\n',
    '        "value: ${{ steps.policy.outputs.final-message }}"\n        in action_text\n',
)
path.write_text(text, encoding="utf-8")

# Correct any legacy-low compatibility test that accidentally kept schema v2.
for test_path in sorted((ROOT / "tests").glob("test_devflow*.py")):
    text = test_path.read_text(encoding="utf-8")
    needle = 'legacy = dict(template)\n    legacy["reasoning_effort"] = "low"'
    replacement = 'legacy = dict(template)\n    legacy["schema_version"] = 1\n    legacy["reasoning_effort"] = "low"'
    if needle in text:
        text = text.replace(needle, replacement)
    test_path.write_text(text, encoding="utf-8")

# Rebase dynamic task facts onto the clean branch and the frozen main baseline.
active_path = ROOT / "docs/implementation/ACTIVE_TASKS.yaml"
active = json.loads(active_path.read_text(encoding="utf-8"))
for item in active.get("tasks", []):
    if item.get("task_id") == "devflow-operational-optimization-v2":
        item.update(
            {
                "status": "RUNNING",
                "branch": CLEAN_BRANCH,
                "pull_request": None,
                "current_stage": "W01",
            }
        )
active_path.write_text(json.dumps(active, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

task_dir = ROOT / "docs/implementation/devflow-operational-optimization-v2"
state_path = task_dir / "task_state.yaml"
state = json.loads(state_path.read_text(encoding="utf-8"))
state.update(
    {
        "state_revision": int(state.get("state_revision", 0)) + 1,
        "status": "RUNNING",
        "execution_status": "RUNNING",
        "security_status": "PENDING",
        "working_branch": CLEAN_BRANCH,
        "pull_request": None,
        "base_sha_at_start": MAIN_SHA,
        "last_product_commit_sha": MAIN_SHA,
        "current_stage": "W01",
        "last_completed_stage": "W00",
        "last_successful_step": "clean_branch_rebuilt_from_frozen_main",
        "next_action": "complete_codex_eligibility_and_zero_model_gates",
        "updated_at_utc": "2026-07-23T17:20:00Z",
    }
)
state.setdefault("gate_results", {})["W00_CODEX_FREEZE"] = "PASS:PR46"
state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Render stable status and handoff using the migrated schema implementation.
run("python", "scripts/devflow/render_task_docs.py", str(task_dir.relative_to(ROOT)))

write(
    "docs/implementation/devflow-operational-optimization-v2/W01_clean_rebuild_plan.md",
    """# W01 Clean Rebuild 计划\n\n## 目标\n\n从已合并全局 Codex Freeze 的最新 `main` 重建干净分支，只移植 PR #44 中仍有效的 XHigh Context Budget、影响感知 Gate、State Schema v2、Branch GC dry-run 和升级兼容实现。\n\n## 排除\n\n- 不移植重复 `codex-thin-worker-v2` Action；\n- 不移植临时 Patch Workflow；\n- 不移植 `*_v2.py` 平行生产实现；\n- 不恢复任何自动 Codex Dispatch 或 Retry；\n- 本阶段 Codex 调用次数为 0。\n""",
)
write(
    "docs/implementation/devflow-operational-optimization-v2/W01_clean_rebuild_result.md",
    """# W01 Clean Rebuild 结果\n\n```yaml\nstatus: PASS_PENDING_GATES\nbase: frozen-main\nsource_pr: 44\ncodex_calls: 0\nduplicate_actions: removed\ntemporary_patch_workflows: excluded\n```\n""",
)

print("CLEAN_MIGRATION=APPLIED")
