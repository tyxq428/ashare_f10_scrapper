# HANDOFF：Codex Trigger Surface Lockdown v2

## 当前检查点

- 任务合同和 W00–W08 总计划已写入仓库；
- Codex Policy 保持 `disabled`；
- 未触发、未重跑任何 Codex Workflow；
- 当前正在审计历史 Run、旧分支、常驻 Workflow 和 Environment 保护边界。

## 恢复入口

```yaml
branch: feature/codex-trigger-surface-lockdown-v2
stage: W00
next_action:
  - produce_trigger_surface_inventory
  - remove_persistent_codex_workflow
  - disable_historical_workflow
  - quarantine_merged_stale_branches
  - enforce_or_document_environment_review_boundary
```
