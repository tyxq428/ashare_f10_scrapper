from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch marker: {label}")
    return text.replace(old, new, 1)


# State Consistency may not synthesize a fake immutable task descriptor.
path = Path(".github/workflows/devflow-auto-recovery.yml")
text = path.read_text(encoding="utf-8")
start_marker = '          if [[ ! -s /tmp/devflow-source-task.yaml && "$SOURCE_NAME" == "Devflow State Consistency" ]]; then\n'
end_marker = "          args=(\n"
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = (
    "          # State Consistency without an immutable task descriptor is not\n"
    "          # eligible for an automatic Codex generation. The Web Supervisor\n"
    "          # must diagnose the actual failing branch and bounded paths first.\n\n"
)
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

# Structured BLOCKED is terminal for the current Codex generation.
path = Path("scripts/devflow/recovery_policy.py")
text = path.read_text(encoding="utf-8")
summary_marker = '    runtime_preflight = _find_summary(artifact_root, "runtime-preflight.json")\n'
text = replace_once(
    text,
    summary_marker,
    summary_marker + '    codex_result = _find_summary(artifact_root, "codex-result.json")\n',
    "codex result summary",
)
infra_marker = "    if conclusion in TERMINAL_INFRA_CONCLUSIONS or _contains_marker(failure_steps, INFRA_STEP_MARKERS):\n"
blocked_policy = '''    if codex_result is not None and codex_result.get("status") == "BLOCKED":
        return _decision(
            action="INTERRUPTED",
            reason_code="CODEX_BLOCKED_NO_RETRY",
            reason="The bounded Codex worker explicitly reported BLOCKED and made no publishable repair.",
            minimum_action=(
                "Use ChatGPT Web Supervisor to inspect the immutable failure context and either repair "
                "directly or create a new correctly scoped task. Do not rerun this Codex generation."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

    if source_workflow == "Devflow State Consistency":
        return _decision(
            action="INTERRUPTED",
            reason_code="STATE_CONSISTENCY_WEB_REPAIR_REQUIRED",
            reason=(
                "State Consistency failures are execution-framework changes and are not eligible for "
                "automatically synthesized Codex repair scopes."
            ),
            minimum_action=(
                "Diagnose and repair the actual failing branch in ChatGPT Web, then rerun deterministic gates."
            ),
            notification_type="INTERRUPTED",
            **common,
        )

'''
text = replace_once(text, infra_marker, blocked_policy + infra_marker, "blocked policy")
text = replace_once(
    text,
    'if source_workflow in {"Devflow Product Gate", "Devflow Post Merge", "Devflow State Consistency"}:',
    'if source_workflow in {"Devflow Product Gate", "Devflow Post Merge"}:',
    "remove state consistency from codex repair",
)
path.write_text(text, encoding="utf-8")

# Restore production action only on the reviewed hotfix branch.
Path(".github/actions/codex-thin-worker/action.yml").write_text(
    '''name: Codex Thin Worker
description: Run one bounded Codex session through the localhost-only Responses forwarder.

inputs:
  api-key:
    description: Private API key supplied by the secret-bearing caller job.
    required: true
  model:
    description: Private model identifier supplied by the secret-bearing caller job.
    required: true
  prompt-file:
    description: Repository-relative trusted task descriptor.
    required: true

outputs:
  final-message:
    description: Structured final Codex message produced under the repository output schema.
    value: ${{ steps.run-codex.outputs.final-message }}

runs:
  using: composite
  steps:
    - id: run-codex
      name: Run one bounded Codex Thin Worker session
      uses: openai/codex-action@52fe01ec70a42f454c9d2ebd47598f9fd6893d56
      with:
        openai-api-key: ${{ inputs.api-key }}
        responses-api-endpoint: http://127.0.0.1:8787/v1/responses
        model: ${{ inputs.model }}
        effort: xhigh
        prompt-file: ${{ inputs.prompt-file }}
        output-schema-file: docs/process/templates/codex_result.schema.json
        sandbox: workspace-write
        safety-strategy: drop-sudo
        allow-bots: "true"
        allow-bot-users: github-actions[bot]
''',
    encoding="utf-8",
)

# Static policy rejects reintroducing synthesized State Consistency tasks.
path = Path("scripts/devflow/validate_workflows.py")
text = path.read_text(encoding="utf-8")
marker = '''        if "issues: write" in text:
            errors.append(f"{path}: auto recovery must not write Issues directly")
'''
replacement = marker + '''        if "Repair the deterministic devflow state or validation failure" in text:
            errors.append(f"{path}: State Consistency must not synthesize a Codex task descriptor")
        if 'SOURCE_NAME" == "Devflow State Consistency"' in text:
            errors.append(f"{path}: State Consistency without immutable context must not dispatch Codex")
'''
path.write_text(replace_once(text, marker, replacement, "workflow validation"), encoding="utf-8")

# Regression tests.
path = Path("tests/test_devflow.py")
text = path.read_text(encoding="utf-8")
if "def test_codex_blocked_result_never_retries" not in text:
    text += r'''


def test_codex_blocked_result_never_retries(tmp_path: Path) -> None:
    (tmp_path / "codex-result.json").write_text(
        json.dumps(
            {
                "status": "BLOCKED",
                "changed_files": [],
                "tests_passed": False,
                "blocking_reason": "scope unavailable",
            }
        ),
        encoding="utf-8",
    )
    decision = classify(
        source_workflow="Codex Task",
        source_run_id=1001,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Enforce runtime, Codex, scope, gate and secret outcomes"),
        artifact_root=tmp_path,
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "CODEX_BLOCKED_NO_RETRY"
    assert decision.notification_type == "INTERRUPTED"


def test_state_consistency_failure_requires_web_supervisor_not_codex() -> None:
    decision = classify(
        source_workflow="Devflow State Consistency",
        source_run_id=1002,
        conclusion="failure",
        run_attempt=1,
        jobs_payload=failed_jobs("Validate devflow workflows and tests"),
    )
    assert decision.action == "INTERRUPTED"
    assert decision.reason_code == "STATE_CONSISTENCY_WEB_REPAIR_REQUIRED"
    assert decision.notification_type == "INTERRUPTED"
'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_devflow_codex_environment.py")
text = path.read_text(encoding="utf-8")
if "def test_auto_recovery_does_not_synthesize_state_consistency_codex_scope" not in text:
    text += r'''


def test_auto_recovery_does_not_synthesize_state_consistency_codex_scope() -> None:
    workflow = REPO / ".github/workflows/devflow-auto-recovery.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "Repair the deterministic devflow state or validation failure" not in text
    assert 'SOURCE_NAME" == "Devflow State Consistency"' not in text
    assert validate_file(workflow) == []
'''
path.write_text(text, encoding="utf-8")

with Path("docs/process/policies/security-and-codex.md").open("a", encoding="utf-8") as handle:
    handle.write('''

## Codex 熔断与 `BLOCKED` 终态

- `codex-result.json.status=BLOCKED` 表示当前 Generation 无法在批准范围内安全修复；不得重跑同一 Codex Job，也不得自动创建相同范围的下一代任务；
- State Consistency、Workflow、安全策略和 Devflow Core 改动默认由 ChatGPT Web Supervisor 直接诊断和修改，不从缺失上下文的失败 Run 合成 Codex Descriptor；
- 只有不可变 Task Descriptor、可复现失败证据、真实失败分支和覆盖失败路径的允许范围同时存在时，才允许自动 Codex Repair；
- 紧急熔断必须在模型调用之前生效，并覆盖默认分支及仍可能被重跑的旧任务分支。
''')

with Path("docs/process/runbooks/automatic-recovery.md").open("a", encoding="utf-8") as handle:
    handle.write('''

## Codex 调用前熔断

1. 若结构化结果是 `BLOCKED`，停止该 Generation；不重跑模型；
2. 若 State Consistency 缺少不可变 Task Descriptor 或真实失败路径不在允许范围，交由 ChatGPT Web 直接修复；
3. 不得从 `main` 合成固定五文件范围来猜测功能分支失败；
4. 修复恢复策略本身时先打开全局熔断，确定性 Gate 全部通过后再恢复模型入口。
''')

with Path("docs/ENGINEERING_ISSUES_AND_LESSONS.md").open("a", encoding="utf-8") as handle:
    handle.write('''

## GHA-021 State Consistency 合成错误范围导致 XHigh Codex 循环

- **现象**：多个 State Consistency 失败被自动转换为 XHigh Codex Recovery；模型反复返回 `BLOCKED`、零变更，但仍被重跑或再次派发。
- **根因**：Auto Recovery 在没有不可变失败 Task Descriptor 时从 `main` 合成固定五文件范围；真实失败位于活动功能分支的新文件和测试中，范围无法覆盖。恢复策略也没有把结构化 `BLOCKED` 视为终态。
- **修复**：删除合成 State Consistency Descriptor；State Consistency 默认交给 ChatGPT Web；读取 `codex-result.json`，`BLOCKED` 立即熔断且禁止重试；根因修复期间关闭生产模型入口。
- **预防规则**：Codex Repair 必须同时具备不可变任务上下文、可复现失败、正确基线和覆盖真实失败路径的允许范围；`BLOCKED` 永远不能自动重试同一 Generation。
''')

Path("docs/implementation/devflow-operational-optimization-v2/W01_HF01_result.md").write_text(
    '''# W01-HF01 结果：Codex Recovery 熔断与范围修复

```yaml
status: PASS
codex_calls_during_hotfix: 0
blocked_result_retry: forbidden
synthetic_state_consistency_descriptor: removed
web_supervisor_direct_repair: enabled
```

四个已知失败恢复分支和默认分支已先行熔断。恢复策略现在读取结构化 Codex 结果，`BLOCKED` 直接终止当前 Generation；State Consistency 不再合成固定五文件 Codex 范围，而由 ChatGPT Web 基于真实分支和失败路径直接修复。
''',
    encoding="utf-8",
)
