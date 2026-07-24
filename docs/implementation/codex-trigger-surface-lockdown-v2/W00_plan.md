# W00 计划：全触发面库存

## 检查项

1. `main` 全仓关键词和 Workflow 依赖图；
2. GitHub Workflow enabled/disabled 状态；
3. 历史 Codex Run 的来源 SHA、Actor、Run attempt 和可重跑边界；
4. 远端分支中的旧 Codex Workflow；
5. 开放 PR 对应分支，防止误删；
6. `agent-runtime` Required Reviewer、Deployment Branch Policy 和 Secret-bearing Workflow；
7. `workflow_dispatch`、`workflow_run`、`repository_dispatch`、Issue 命令和临时 Workflow；
8. 当前静态 Validator 未覆盖的触发面。

## 输出

```text
CODEx_TRIGGER_SURFACE_AUDIT.json
W00_result.md
branch_quarantine_plan.json
workflow_lock_plan.json
environment_boundary_result.json
```

## Gate

```yaml
codex_calls: 0
secrets_read: false
unsafe_branch_mutations: 0
inventory_complete: true
```
