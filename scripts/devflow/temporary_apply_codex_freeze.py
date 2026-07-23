from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

policy = {
    "schema_version": 1,
    "mode": "disabled",
    "manual_approval_required": True,
    "allowed_actors": ["tyxq428"],
    "auto_recovery_dispatch": False,
    "allow_github_actions_bot": False,
    "retry_failed_codex_job": False,
    "limits": {
        "calls_per_task": 1,
        "calls_per_fingerprint": 1,
        "recovery_generations": 0,
        "automatic_second_session": 0,
    },
    "terminal_results": ["BLOCKED", "NO_CHANGES", "UNVERIFIED", "FAILURE", "TIMEOUT"],
    "freeze_reason": "User-directed zero-Codex optimization window",
    "frozen_at_utc": "2026-07-23T16:50:00Z",
}
policy_path = ROOT / ".devflow/codex-policy.yaml"
policy_path.parent.mkdir(parents=True, exist_ok=True)
policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

action = ROOT / ".github/actions/codex-thin-worker/action.yml"
action.write_text(
    """name: Codex Thin Worker\n"
    "description: Repository-wide disabled-mode circuit breaker; never invokes a model while the policy is frozen.\n\n"
    "inputs:\n"
    "  api-key:\n"
    "    description: Unused while the repository Codex policy is disabled.\n"
    "    required: true\n"
    "  model:\n"
    "    description: Unused while the repository Codex policy is disabled.\n"
    "    required: true\n"
    "  prompt-file:\n"
    "    description: Trusted task descriptor retained only for a safe blocked result.\n"
    "    required: true\n\n"
    "outputs:\n"
    "  final-message:\n"
    "    description: Structured BLOCKED result emitted before any model invocation.\n"
    "    value: ${{ steps.policy.outputs.final-message }}\n\n"
    "runs:\n"
    "  using: composite\n"
    "  steps:\n"
    "    - id: policy\n"
    "      name: Stop before Codex model invocation\n"
    "      shell: bash\n"
    "      run: |\n"
    "        set -euo pipefail\n"
    "        delimiter=CODEX_POLICY_RESULT_${RANDOM}_${RANDOM}\n"
    "        {\n"
    "          echo \"final-message<<${delimiter}\"\n"
    "          echo '{\"status\":\"BLOCKED\",\"changed_files\":[],\"commands_run\":[],\"tests_passed\":false,\"summary\":\"Codex is disabled by repository policy.\",\"blocking_reason\":\"CODEX_POLICY_DISABLED\"}'\n"
    "          echo \"${delimiter}\"\n"
    "        } >> \"$GITHUB_OUTPUT\"\n"
    "        echo \"CODEX_MODEL_INVOCATION=DISABLED\" >> \"$GITHUB_STEP_SUMMARY\"\n"
    """,
    encoding="utf-8",
)

validator = ROOT / "scripts/devflow/validate_workflows.py"
text = validator.read_text(encoding="utf-8")
marker = "def validate_file(path: Path) -> list[str]:\n"
helper = '''def _codex_policy_mode() -> str:\n    path = Path(".devflow/codex-policy.yaml")\n    try:\n        value = json.loads(path.read_text(encoding="utf-8"))\n    except (OSError, json.JSONDecodeError) as exc:\n        raise ValueError("cannot load .devflow/codex-policy.yaml") from exc\n    mode = value.get("mode")\n    if mode not in {"disabled", "enabled"}:\n        raise ValueError("codex policy mode must be disabled or enabled")\n    return mode\n\n\n'''
if helper not in text:
    text = text.replace(marker, helper + marker, 1)
start = text.index('    if path.as_posix().endswith(".github/actions/codex-thin-worker/action.yml"):\n')
end = text.index('    if path.name == "devflow-auto-recovery.yml":\n', start)
replacement = '''    if path.as_posix().endswith(".github/actions/codex-thin-worker/action.yml"):\n        try:\n            mode = _codex_policy_mode()\n        except ValueError as exc:\n            errors.append(f"{path}: {exc}")\n            mode = "invalid"\n        if mode == "disabled":\n            _require_fragments(\n                path,\n                text,\n                (\n                    "using: composite",\n                    "CODEX_POLICY_DISABLED",\n                    "CODEX_MODEL_INVOCATION=DISABLED",\n                    "value: ${{ steps.policy.outputs.final-message }}",\n                ),\n                errors,\n            )\n            if "openai/codex-action@" in text:\n                errors.append(f"{path}: disabled policy must stop before the official Codex action")\n        elif mode == "enabled":\n            _require_fragments(\n                path,\n                text,\n                (\n                    "using: composite",\n                    "openai/codex-action@52fe01ec70a42f454c9d2ebd47598f9fd6893d56",\n                    "http://127.0.0.1:8787/v1/responses",\n                    "effort: xhigh",\n                    "safety-strategy: drop-sudo",\n                    "value: ${{ steps.run-codex.outputs.final-message }}",\n                    "${{ inputs.api-key }}",\n                    "${{ inputs.model }}",\n                ),\n                errors,\n            )\n        if "secrets." in text:\n            errors.append(f"{path}: composite action must receive explicit inputs, not read secrets directly")\n        if "output-file:" in text:\n            errors.append(\n                f"{path}: official action output must be handed off through final-message, not an absolute output-file"\n            )\n        if "allow-users:" in text:\n            errors.append(f"{path}: arbitrary user allowlists are forbidden")\n        if "effort: low" in text:\n            errors.append(f"{path}: production Codex sessions must use xhigh reasoning")\n\n'''
text = text[:start] + replacement + text[end:]
validator.write_text(text, encoding="utf-8")

tests = ROOT / "tests/test_devflow_codex_environment.py"
text = tests.read_text(encoding="utf-8")
start = text.index("def test_reusable_unit_allows_only_trusted_repository_bot_and_uses_xhigh() -> None:\n")
end = text.index("\n\ndef test_new_task_template_defaults_xhigh", start)
replacement = '''def test_reusable_unit_stops_before_model_when_policy_is_disabled() -> None:\n    action = REPO / ".github/actions/codex-thin-worker/action.yml"\n    text = action.read_text(encoding="utf-8")\n    policy = json.loads((REPO / ".devflow/codex-policy.yaml").read_text(encoding="utf-8"))\n    assert policy["mode"] == "disabled"\n    assert "using: composite" in text\n    assert "CODEX_POLICY_DISABLED" in text\n    assert "CODEX_MODEL_INVOCATION=DISABLED" in text\n    assert "openai/codex-action@" not in text\n    assert "secrets." not in text\n    assert validate_file(action) == []\n'''
text = text[:start] + replacement + text[end:]
text = text.replace(
    '    assert "value: ${{ steps.run-codex.outputs.final-message }}" in action_text\n',
    '    assert "value: ${{ steps.policy.outputs.final-message }}" in action_text\n',
)
tests.write_text(text, encoding="utf-8")

policy_doc = ROOT / "docs/process/policies/security-and-codex.md"
text = policy_doc.read_text(encoding="utf-8")
section = '''\n\n## 用户级零额度冻结\n\n仓库级 `.devflow/codex-policy.yaml` 是模型调用总开关。`mode: disabled` 时，Composite Action 必须在任何 Endpoint、Forwarder 或模型步骤之前返回 `CODEX_POLICY_DISABLED`，并且不得引用 `openai/codex-action`。冻结期间不得由 Bot、Auto Recovery、失败 Job 重跑或人工误触发绕过。解除冻结必须通过经过审查的 Policy 变更，并绑定一次性任务授权。\n'''
if "## 用户级零额度冻结" not in text:
    policy_doc.write_text(text.rstrip() + section + "\n", encoding="utf-8")

plan_dir = ROOT / "docs/implementation/devflow-operational-optimization-v2"
plan_dir.mkdir(parents=True, exist_ok=True)
(plan_dir / "W00_codex_freeze_plan.md").write_text(
    """# W00-Codex-Freeze 计划\n\n## 目标\n\n在整个 operational optimization 完成前，将仓库 Codex 模型入口确定性熔断，确保任何误触发、旧任务重跑或 Bot 调度都不会产生模型调用。\n\n## 验收\n\n- `.devflow/codex-policy.yaml` 为 `mode: disabled`；\n- Composite Action 不引用 `openai/codex-action`；\n- 返回结构化 `CODEX_POLICY_DISABLED`；\n- Workflow 静态校验、Ruff 和定向 pytest 通过；\n- 本工作包 Codex 调用次数为 0。\n""",
    encoding="utf-8",
)
(plan_dir / "W00_codex_freeze_result.md").write_text(
    """# W00-Codex-Freeze 结果\n\n```yaml\nstatus: PASS_PENDING_PR_GATES\ncodex_calls: 0\npolicy_mode: disabled\nmodel_action_reference_present: false\n```\n\n冻结由确定性脚本实施；合并后保持默认禁用，直至用户对某个具体任务另行授权。\n""",
    encoding="utf-8",
)

print("CODEX_FREEZE_PATCH=APPLIED")
