# W00-Codex-Freeze 计划

## 目标

在整个 operational optimization 完成前，将仓库 Codex 模型入口确定性熔断，确保任何误触发、旧任务重跑或 Bot 调度都不会产生模型调用。

## 验收

- `.devflow/codex-policy.yaml` 为 `mode: disabled`；
- Composite Action 不引用 `openai/codex-action`；
- 返回结构化 `CODEX_POLICY_DISABLED`；
- Workflow 静态校验、Ruff 和定向 pytest 通过；
- 本工作包 Codex 调用次数为 0。
