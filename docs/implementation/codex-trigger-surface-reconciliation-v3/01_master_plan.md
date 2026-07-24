# 总计划：Codex Trigger Surface Reconciliation v3

## 决策路径

差异对账确认：PR #52 已完成绝大多数 lockdown-v2 目标；当前没有应重复实施的代码缺口。唯一无法由现有 GitHub 连接器读取或修改的项目，是 `agent-runtime` Environment 的 Required Reviewer、管理员绕过和部署分支保护元数据。因此采用“差异收敛 + 平台人工配置”路径。

## W00｜差异对账与旧任务收敛

- 对比 PR #52、canonical main 与 lockdown-v2 计划；
- 生成完整差异矩阵；
- 证明旧分支只有计划文档、没有待合并实现；
- 决定保留 eligibility-only `codex-task.yml`；
- 将旧 lockdown-v2 标记为被 PR #52 / reconciliation-v3 取代。

## W01｜Environment 平台保护确认

由用户在 GitHub UI 核验并配置 `agent-runtime`：

1. Required reviewers 包含 `tyxq428`；
2. 若只有单一维护者，保留可自审，否则任务将无法由同一账号启动与批准；
3. 可用时关闭管理员绕过；
4. Deployment branches 至少限制为 `main`；
5. 不查看、复制或测试任何 Secret 值。

当前连接器没有 Environment 管理/读取权限，因此此阶段必须 Fail Closed 为 `WAITING_HUMAN`。

## W02｜人工确认后的最终收尾

- 记录用户的 GitHub UI 配置确认；
- 不触发 Relay Health、Secret Audit、Codex 或 Responses 探针；
- 更新 W01/W02 结果、FINAL_REPORT、STATUS、HANDOFF 与 ACTIVE_TASKS；
- Codex Policy 最终保持 `disabled`。

## Gate

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
main_implementation_changes: 0
platform_protection_confirmed: human_attestation_required
```
