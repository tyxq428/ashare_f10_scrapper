# W01 计划：XHigh 指令一致性与 Context Budget

## 目标

1. 修复根 `AGENTS.md` 的 `low effort` 漂移；
2. 确保所有权威文档将 XHigh 定义为生产运行时策略；
3. 保持历史 Low Descriptor 的只读兼容，但禁止其降低真实模型强度；
4. 在调用 Codex 前执行确定性 Context Budget 检查。

## 允许修改

- `AGENTS.md`；
- `.github/AGENTS.md`；
- `.github/actions/codex-thin-worker/action.yml`（只验证/注释，不降低 XHigh）；
- `.github/workflows/codex-task.yml`；
- `docs/process/policies/security-and-codex.md`；
- `docs/process/runbooks/run-codex-thin-worker.md`；
- `docs/process/templates/codex_task.template.yaml`；
- `scripts/devflow/task_descriptor.py`；
- `scripts/devflow/context_budget.py`；
- `scripts/devflow/validate_workflows.py`；
- `tests/test_devflow.py`；
- `tests/test_devflow_codex_environment.py`；
- 本任务目录。

## Context Budget 默认值

```yaml
max_allowed_files: 5
max_task_bytes: 32768
max_total_allowed_file_bytes: 262144
max_single_file_bytes: 131072
max_log_excerpt_lines: 300
include_chat_history: false
include_full_sop: false
```

未知/缺失值使用以上保守默认；超限在 Forwarder/Codex Action 前失败，不产生模型 Token。

## Gate

- Root Agent Contract 与 Composite Action 均为 XHigh；
- Task Descriptor 新默认只能是 XHigh；
- 历史 schema-v1 Low Descriptor 可解析，但 Runtime 仍由 Composite Action XHigh 强制；
- Context Budget 的 PASS/FAIL、路径缺失、超大单文件和总字节数均有回归测试；
- Secret 值、Prompt 全文、聊天历史和完整 SOP 不进入 Context Budget 报告。
