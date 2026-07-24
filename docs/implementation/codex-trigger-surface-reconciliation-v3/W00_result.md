# W00 结果：Lockdown v2 与 PR #52 差异对账

```yaml
status: PASS
path_decision: PLATFORM_CONFIGURATION_REQUIRED
legacy_branch_open_prs: 0
legacy_branch_changed_files: 7
docs_only_legacy_changes: true
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
```

## 差异矩阵

| lockdown-v2 计划项 | PR #52 是否已完成 | 当前实现 | 是否仍是风险 | 分类与建议 |
|---|---|---|---|---|
| 当前 main 不存在常驻模型执行 Workflow/Action | 是 | `codex-task.yml` 为 eligibility-only；Entrypoint Manifest 明确 `model_invocation=false` | 否 | `COMPLETED_BY_PR52` |
| 删除常驻 `codex-task.yml` | 否，采用替代设计 | Workflow 仅做零 Token 候选检查，不绑定 Environment、不读 Secret、不启动 Forwarder | 否 | `SUPERSEDED_BY_SAFER_DESIGN`：保留，便于标准化审计 |
| 删除禁用 Composite Action | 否，保留 fail-closed Action | Action 被静态校验为无模型、无 Secret | 否 | `SUPERSEDED_BY_SAFER_DESIGN` |
| GitHub 平台禁用 `Codex Task` Workflow | 未能由当前连接器核验 | 默认分支定义即使 active 也只有零 Token 检查 | 不构成模型风险 | `UNNECESSARY`：记录平台状态即可，不依赖它保障安全 |
| 历史 Run 重放隔离 | 是 | 88 个历史 `task/codex-*` 分支移除 Descriptor并安装禁用 Action；有持续审计 | 否 | `COMPLETED_BY_PR52` |
| 删除已合并历史分支 | 未删除，采用隔离 | 保留可审计分支但消除模型引用与 Descriptor | 否 | `SUPERSEDED_BY_SAFER_DESIGN`：隔离优于不可逆批量删除 |
| 开放 PR 分支保护 | 是 | 历史分支审计明确不修改开放 PR 分支 | 否 | `COMPLETED_BY_PR52` |
| Relay Health 默认零请求 | 是 | 默认 `configuration_only`，只做本地预检 | 否 | `COMPLETED_BY_PR52` |
| Relay Health 付费探针永久删除 | 否，保留显式诊断 | 人工派发、精确确认、用途必填、仅 run attempt 1；Auto Recovery不监听 | 受控显式请求面 | `SUPERSEDED_BY_SAFER_DESIGN`：保留但本任务不执行 |
| Secret Audit 在 Environment 前验证来源 | 是 | 只接受已完成的一次性 Activation、main、手工派发和模型启动标记 | 否 | `COMPLETED_BY_PR52` |
| Auto Recovery 不重试 Codex/Relay | 是 | 只对可信 pre-model 基础设施故障有限重跑；明确排除 Relay Health 和模型路径 | 否 | `COMPLETED_BY_PR52` |
| Product/Post-Merge/State 失败不调用 Codex | 是 | 统一转 ChatGPT Web / 人工，不创建 Recovery Generation | 否 | `COMPLETED_BY_PR52` |
| 全仓静态模型触发面扫描 | 是 | Validator 扫描 Workflow、Forwarder、自动 Dispatch、Recovery 和 Environment allowlist | 否 | `COMPLETED_BY_PR52` |
| `agent-runtime` Required Reviewer | 当前连接器无法读取/修改 | 仓库只证明引用它的 Workflow 是 Relay Health 与 Secret Audit | 防御纵深待平台确认 | `PLATFORM_CONFIGURATION_REQUIRED` |
| 禁止管理员绕过 Environment | 当前连接器无法读取/修改 | 无仓库内可验证证据 | 防御纵深待平台确认 | `PLATFORM_CONFIGURATION_REQUIRED` |
| Deployment branches 限制为 main | 当前连接器无法读取/修改 | 两个 Workflow 均显式 checkout main，但 Environment 本身策略未知 | 防御纵深待平台确认 | `PLATFORM_CONFIGURATION_REQUIRED` |
| W05 静态/行为回归 | 是 | PR #52 forced pre-merge 与 exact-main 均通过 | 否 | `COMPLETED_BY_PR52` |
| W06 文档与控制平面 | 是 | Policy、Runbook、Entrypoint Manifest 与持续审计已落库 | 否 | `COMPLETED_BY_PR52` |
| W07/W08 完整 Test、688521 E2E、exact-main | 是 | PR #52 与 Run 30067491515 完成 | 否 | `COMPLETED_BY_PR52` |

## `codex-task.yml` 决策

**保留 eligibility-only Workflow。**

理由：它当前只有 owner 手工 dispatch、只读权限、精确 main 控制面和 data-only 任务分支检查；最终明确输出 `CODEX_MODEL_INVOCATION=DISABLED`。删除它不会减少模型触发面，反而会失去统一、可审计的零 Token 候选检查入口。真正模型执行仍需要新的受审一次性 Activation PR。

## 平台状态结论

- 当前连接器不能读取 GitHub Actions Workflow 的平台 `active/disabled_manually` 元数据；
- 但当前默认分支 `Codex Task` 即使 active，也无法读取 Secret或调用模型；
- 历史模型定义的重放风险已由 PR #52 的分支隔离和持续审计处理；
- 因此 Workflow平台状态不再是模型安全前提。

## Environment 结论

当前连接器不具备 Environment 管理/读取接口，无法核验 Required Reviewer、管理员绕过和部署分支保护。该项不能用代码或文档代替，进入 W01 `WAITING_HUMAN`。
