# 任务合同：Codex Trigger Surface Reconciliation v3

## 目标

仅处理 `feature/codex-trigger-surface-lockdown-v2` 与已完成任务 `codex-trigger-surface-audit-v2` / PR #52 之间仍未闭合的真实差异，不重复 PR #52 已交付的历史分支隔离、零模型入口、Relay 付费探针边界、Secret Audit 前置验证与全仓静态扫描。

## 硬约束

```yaml
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
model_workflow_dispatches: 0
```

## 当前范围

1. 固化 lockdown-v2 与 PR #52 的逐项差异矩阵；
2. 决定 `codex-task.yml` 的保留或删除；
3. 区分默认分支源码、GitHub Workflow 平台状态、历史 Run 定义与历史分支；
4. 核验 `agent-runtime` Environment 的保护元数据；
5. 仅对 `STILL_REQUIRED` 与 `PLATFORM_CONFIGURATION_REQUIRED` 项继续推进。

## 完成定义

- 旧 lockdown-v2 分支被明确标记为由 PR #52 与本任务取代，不再作为活动任务；
- `codex-task.yml` 的最终架构决策有可审计依据；
- 平台层未能由当前连接器读取的 Environment 保护规则进入真实 `WAITING_HUMAN`；
- 不读取、显示、复制或测试任何 Environment Secret；
- 用户完成最小 GitHub UI 配置并确认后，任务可从 W01 恢复并完成最终记录。
