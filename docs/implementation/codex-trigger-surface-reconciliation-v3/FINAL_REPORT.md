# Codex Trigger Surface Reconciliation v3 最终报告

## 1. 总结

`feature/codex-trigger-surface-lockdown-v2` 属于孤立、重复且未进入实现的历史任务。它相对当时 main 仅包含任务合同、计划和状态文档，没有 Workflow、Action、脚本、产品代码或测试实现，也没有开放 PR。

其仓库代码、历史 Workflow Re-run、历史任务分支、Relay 付费探针、Secret Audit 来源边界和永久静态守卫目标已由 `codex-trigger-surface-audit-v2` / PR #52 完成。剩余唯一真实差异是 GitHub 平台 Environment 保护元数据，并已由用户通过 GitHub UI 完成确认。

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
post_merge: PASS
pull_request: 53
merge_sha: 49f39ce2ff5eed1ac06be8dbd5de1cc3949530b7
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
implementation_files_changed: 0
human_action_remaining: false
```

## 2. 与 PR #52 的完整差异矩阵

| lockdown-v2 计划项 | PR #52 是否已完成 | 当前实现 | 是否仍是风险 | 分类与建议 |
|---|---|---|---|---|
| 当前 main 不存在常驻模型执行 Workflow/Action | 是 | `codex-task.yml` 为 eligibility-only；Entrypoint Manifest 明确 `model_invocation=false` | 否 | `COMPLETED_BY_PR52` |
| 删除常驻 `codex-task.yml` | 否，采用替代设计 | Workflow 仅做零 Token 候选检查，不绑定 Environment、不读 Secret、不启动 Forwarder | 否 | `SUPERSEDED_BY_SAFER_DESIGN`：保留，便于标准化审计 |
| 删除禁用 Composite Action | 否，保留 fail-closed Action | Action 被静态校验为无模型、无 Secret | 否 | `SUPERSEDED_BY_SAFER_DESIGN` |
| GitHub 平台禁用 `Codex Task` Workflow | 未作为安全前提 | 用户确认平台状态为 active；当前定义只能执行零 Token 检查 | 不构成模型风险 | `UNNECESSARY`：保留 active eligibility-only Workflow |
| 历史 Run 重放隔离 | 是 | 88 个历史 `task/codex-*` 分支移除 Descriptor并安装禁用 Action；有持续审计 | 否 | `COMPLETED_BY_PR52` |
| 删除已合并历史分支 | 未删除，采用隔离 | 保留可审计分支但消除模型引用与 Descriptor | 否 | `SUPERSEDED_BY_SAFER_DESIGN`：隔离优于不可逆批量删除 |
| 开放 PR 分支保护 | 是 | 历史分支审计明确不修改开放 PR 分支 | 否 | `COMPLETED_BY_PR52` |
| Relay Health 默认零请求 | 是 | 默认 `configuration_only`，只做本地预检 | 否 | `COMPLETED_BY_PR52` |
| Relay Health 付费探针永久删除 | 否，保留显式诊断 | 人工派发、精确确认、用途必填、仅 run attempt 1；Auto Recovery不监听 | 受控显式请求面 | `SUPERSEDED_BY_SAFER_DESIGN`：保留但本任务不执行 |
| Secret Audit 在 Environment 前验证来源 | 是 | 只接受已完成的一次性 Activation、main、手工派发和模型启动标记 | 否 | `COMPLETED_BY_PR52` |
| Auto Recovery 不重试 Codex/Relay | 是 | 明确排除 Relay Health 和模型路径 | 否 | `COMPLETED_BY_PR52` |
| Product/Post-Merge/State 失败不调用 Codex | 是 | 统一转 ChatGPT Web / 人工，不创建 Recovery Generation | 否 | `COMPLETED_BY_PR52` |
| 全仓静态模型触发面扫描 | 是 | Validator 扫描 Workflow、Forwarder、自动 Dispatch、Recovery 和 Environment allowlist | 否 | `COMPLETED_BY_PR52` |
| `agent-runtime` Required Reviewer | 用户已完成 | Required reviewers 为 `tyxq428`、`jellycookie` | 否 | `PLATFORM_CONFIGURATION_REQUIRED` → 已人工完成 |
| 禁止管理员绕过 Environment | 用户已完成 | 管理员绕过未启用 | 否 | `PLATFORM_CONFIGURATION_REQUIRED` → 已人工完成 |
| Deployment branches 限制为 main | 用户已完成 | Selected branches and tags，仅允许 `main` | 否 | `PLATFORM_CONFIGURATION_REQUIRED` → 已人工完成 |
| Prevent self-review | 用户选择不启用 | self-review 允许；仍保留显式 Environment 审批 | 不构成自动触发面；不强制双人分离 | `UNNECESSARY`：按用户决策保留 self-review |
| W05 静态/行为回归 | 是 | PR #52 forced pre-merge 与 exact-main 均通过 | 否 | `COMPLETED_BY_PR52` |
| W06 文档与控制平面 | 是 | Policy、Runbook、Entrypoint Manifest 与持续审计已落库 | 否 | `COMPLETED_BY_PR52` |
| W07/W08 完整 Test、688521 E2E、exact-main | 是 | PR #52 已完成；PR #53 精确 head 的 Test、E2E、State Consistency 也全部通过 | 否 | `COMPLETED_BY_PR52`，本任务仅补充文档 Gate |
| 通过实际模型、Relay或历史 Re-run验证 | 未执行 | 仅使用静态证据、GitHub UI 元数据与确定性 Gate | 执行会违反硬约束 | `UNSAFE_TO_AUTOMATE`：继续禁止 |

`STILL_REQUIRED` 的仓库代码项目数量为 0。

## 3. Codex Thin Worker 触发面

### 当前默认分支

模型可达触发面为 0：

- `.devflow/codex-policy.yaml` 为 `mode: disabled`；
- 唯一常驻 `codex-task.yml` 为 eligibility-only；
- `model_invocation=false`；
- 不绑定 `agent-runtime`；
- 不读取 Secret；
- 不启动 Forwarder；
- 不包含模型 Action；
- 自动 Dispatch、自动重试与 Recovery Generation均为 0。

### 历史 Run

历史 Run 的不可变 Workflow 定义仍可能包含旧模型 Job，但 PR #52 已对 88 个历史输入分支实施 fail-closed quarantine并加入永久审计。因此历史定义仍是审计证据，但历史模型执行路径已在输入分支层关闭。

## 4. Responses 付费请求面

- 自动 Responses 付费请求面：0；
- 自动重试或 GitHub UI rerun 付费请求面：0；
- 人工显式诊断入口：保留 1 个，即 Relay Health 的 `paid_responses_probe` 模式；
- 本任务付费探针次数：0。

Relay Health 默认是 `configuration_only`，不会发送请求。付费模式需要 owner 人工选择、精确确认短语、非空用途且必须是首次 run attempt。

## 5. `codex-task.yml` 最终决策

**保留 eligibility-only Workflow，并保持平台 active。**

保留方案比删除更安全、可维护、可审计，因为它提供统一的零 Token 候选复核入口，并由 Validator持续约束为：精确 main 控制面、data-only任务分支、只读权限、零 Secret、零模型。

真正模型调用仍必须通过独立、受审、一次性的 Activation PR，不得由常驻 Workflow恢复模型 Job。

## 6. GitHub Workflow 平台状态

```yaml
codex_task_platform_state: active
workflow_dispatch_button_present: true
current_default_branch_definition: eligibility_only
model_invocation_from_current_definition: false
historical_run_definitions: immutable
historical_input_branches: quarantined_88_of_88
```

本任务没有点击 `Run workflow`，也没有执行任何 Re-run。

## 7. `agent-runtime` Environment 保护

```yaml
required_reviewers:
  - tyxq428
  - jellycookie
prevent_self_review: false
self_review_allowed: true
administrator_bypass: disabled
deployment_branch_policy: selected_branches_and_tags
allowed_branches:
  - main
secret_values_opened_or_modified: false
```

当前配置提供显式人工 Environment 审批，但由于 self-review 被允许，不强制双人分离审批。这是用户明确选择，未来若需要四眼审批，可启用 `Prevent self-review`。

当前仓库只允许 Relay Health 与 Secret Audit引用 `agent-runtime`。未来一次性 Activation仍建议使用独立受保护 Environment和独立/短期凭据，不复制当前长期 Secret。

## 8. 遗留分支处理结果

`feature/codex-trigger-surface-lockdown-v2`：

- 无开放 PR；
- 无未合并实现代码；
- 未直接合并；
- 已在其分支上标记为 `DONE / SUPERSEDED_BY_PR52`；
- 不再继续 W01–W08；
- 保留为只读历史审计证据，不盲目删除。

## 9. PR、Merge SHA 与 Gate

```yaml
pull_request: 53
pr_head_sha: c234a6036d6357661bb18c8e425d29d4e3c8ab2b
merge_sha: 49f39ce2ff5eed1ac06be8dbd5de1cc3949530b7
pr_head_gate_runs:
  test: 30071385184
  e2e_688521: 30071385102
  state_consistency: 30071385151
exact_main_source_verification_sha: 49f39ce2ff5eed1ac06be8dbd5de1cc3949530b7
```

三个 PR head Gate 均为 PASS。合并后在精确 Merge SHA上确认 Policy仍为 disabled、唯一入口仍为 eligibility-only、实现文件变更为 0。

## 10. 成本与安全计数

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
model_workflow_dispatches: 0
unsafe_branch_deletions: 0
```

## 11. 人工操作状态

人工配置已完成，没有剩余 HUMAN_REQUIRED。任务不需要新的 Codex、Relay、Responses、Secret Audit或历史 Workflow操作。

## 12. 最终结论

lockdown-v2 已作为重复任务安全收敛；PR #52 提供仓库和历史执行面防护，PR #53 完成差异对账与 GitHub Environment 平台配置确认。最终 Codex Policy保持 `disabled`，自动 Codex与自动付费 Responses触发面均为 0。
