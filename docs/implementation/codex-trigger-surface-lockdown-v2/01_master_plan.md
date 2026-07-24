# 总计划：Codex Trigger Surface Lockdown v2

## 审计假设

当前默认分支已经移除自动 Codex 路径，但源码禁用不等于平台级历史执行面完全消失。此次补充审计覆盖：

- 默认分支中的常驻 Workflow、Composite Action、脚本和文档；
- 历史 Actions Run 的 `Re-run all jobs` / `Re-run failed jobs` 能力；
- 仍指向旧提交的远端 `task/codex-*`、`codex/*`、`recovery/*`、`fix/codex*` 和临时分支；
- `agent-runtime` Environment 的审批和部署边界；
- GitHub Actions Workflow 的仓库级 enabled/disabled 状态；
- Secret Audit、Relay Health 等虽不调用模型但仍访问 Environment 的邻接路径。

## 工作包

### W00｜全触发面库存与不可变证据

- 生成当前 `main`、全部远端分支、历史危险 Workflow 和平台状态清单；
- 将每条路径分类为 `MODEL_CAPABLE / SECRET_ONLY / ZERO_TOKEN / DEAD_CODE / HISTORICAL_RERUN`；
- 明确哪些风险无法仅靠代码修改关闭。

### W01｜移除常驻 Codex Workflow 入口

- 删除常驻 `.github/workflows/codex-task.yml`；
- 删除仅为该入口服务的禁用 Composite Action；
- 保留离线 CLI 资格检查和一次性 Activation 模板；
- 未来模型调用必须由新的受审 Activation PR 创建一次性 Workflow。

### W02｜仓库级 Workflow Lock

- 通过 GitHub Actions API 将历史 `Codex Task` Workflow 设为 `disabled_manually`；
- 新增平台状态校验，要求该 Workflow 不存在或处于 disabled；
- 验证手工 dispatch 和历史 rerun 均不能进入模型。

### W03｜历史分支隔离

- 枚举所有远端分支；
- 对已合并、无开放 PR 的受管旧分支执行删除；
- 对不能安全删除的分支生成 Fail-Closed 报告并禁止作为 Activation 来源；
- 任何旧分支不得保留可调用 `openai/codex-action` 的 Workflow。

### W04｜Environment 人工审批边界

- 检查 `agent-runtime` 当前保护规则；
- 优先设置 Required Reviewer 为仓库所有者、禁止无审批 Secret Job；
- 若 GitHub Token/API 无法修改 Environment 设置，则将模型 Activation 绑定到一个未来新建的受保护 Environment，并把旧 Environment 标记为仅健康/审计用途；
- 不读取、复制或显示任何 Secret 值。

### W05｜静态和行为回归

新增回归覆盖：

```text
old_run_rerun
old_branch_push
manual_dispatch
bot_dispatch
product_gate_failure
post_merge_failure
state_consistency_failure
secret_audit_completion
relay_health_failure
workflow_reenable_without_review
```

所有场景预期模型调用为 0。

### W06｜文档和控制平面收敛

- 更新 Security、Monitoring、Runbook、Entrypoint Manifest；
- 删除过期“常驻 eligibility workflow”描述；
- 明确未来唯一流程为一次性 Activation PR + Environment Approval + One-time Grant。

### W07｜合并前完整验证

- Entrypoint/branch/workflow-state audit；
- State、Docs、Ruff、pytest、Upgrade Compatibility；
- 完整产品 Test；
- 真实 688521 E2E；
- 确认 Codex 调用为 0。

### W08｜合并后 exact-main 与收尾

- 合并 PR；
- 在 exact `main` 重跑所有关键 Gate 与真实 E2E；
- 复核 Workflow disabled 状态和受管分支清单；
- 写 W00–W08 结果、FINAL_REPORT、DONE 状态。

## 风险处置原则

- 不通过“尝试调用 Codex 看是否被阻止”验证；
- 不重跑任何历史 Codex Run；
- 不读取 Relay Secret；
- 平台设置变更若需要人工权限，只允许产生一次明确的 `HUMAN_REQUIRED`，不得用代码假装成功；
- 删除远端分支前必须证明已合并且没有开放 PR。
