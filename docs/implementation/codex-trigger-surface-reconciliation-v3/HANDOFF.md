# Handoff：Codex Trigger Surface Reconciliation v3

## 当前状态

W00 差异对账已完成。PR #52 已覆盖 lockdown-v2 的全部仓库代码与历史分支安全目标；没有需要重复实施的代码缺口。任务停在 W01 的真实 GitHub Environment 平台配置门槛。

## 不要执行

- 不运行 Codex Task；
- 不运行 Relay Health；
- 不运行 Secret Audit；
- 不执行 Responses paid probe；
- 不读取或修改 Environment Secrets；
- 不继续实施旧 lockdown-v2 的 W01–W08；
- 不删除 eligibility-only `codex-task.yml`。

## 唯一恢复条件

用户确认：

```text
agent-runtime 已配置 Required Reviewer=tyxq428、仅允许 main，并已关闭可用的管理员绕过；未读取或修改 Secret。
```

## 恢复后动作

1. 将 W01 标记 PASS；
2. 写 W02 计划与结果、FINAL_REPORT；
3. 更新 task_state、STATUS、HANDOFF 和 ACTIVE_TASKS；
4. 将旧 lockdown-v2 分支标记为由 PR #52 和 reconciliation-v3 取代；
5. 以文档/状态 PR 完成收尾，不运行模型、Relay 或真实 E2E。
