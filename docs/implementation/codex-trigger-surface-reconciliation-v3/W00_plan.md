# W00 计划：差异对账与旧任务收敛

## 输入

- PR #52 与 `codex-trigger-surface-audit-v2` 最终状态；
- 当前 main 的 Codex Policy、Entrypoint Manifest 与相关 Workflows；
- `feature/codex-trigger-surface-lockdown-v2` 的合同、计划和状态文档；
- 开放 PR、分支差异与现有连接器能力。

## 验收

1. 逐项矩阵覆盖 lockdown-v2 的 W00–W08；
2. 每项只使用指定分类；
3. 明确 `codex-task.yml` 的最终决策；
4. 明确自动 Codex 与 Responses 付费请求面；
5. 无代码实现、无 Secret 读取、无模型或付费请求；
6. 旧分支只有文档差异且没有开放 PR；
7. 平台元数据不可读取时生成唯一最小人工动作。
