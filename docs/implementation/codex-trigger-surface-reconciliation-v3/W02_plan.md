# W02 计划：文档收尾、合并与 exact-main 验证

## 目标

在人工 Environment 配置已确认后，仅完成 canonical state 与审计文档收尾，不新增 Workflow、Action、脚本或产品实现，不触发任何模型或付费请求。

## 执行步骤

1. 将 W01 平台配置确认写入仓库；
2. 更新 `DECISIONS.md`、`task_state.yaml`、`STATUS.md`、`HANDOFF.md` 与 `ACTIVE_TASKS.yaml`；
3. 将 PR #53 从 Draft 转为 Ready；
4. 等待 PR 精确 head 上的确定性 GitHub Checks 完成；
5. 合并 PR #53；
6. 在 exact `main` 记录 Merge SHA 与自动触发的确定性 Gate Run；
7. 写入 `W02_result.md`、`FINAL_REPORT.md`，并将任务状态更新为 `DONE`；
8. 最终确认 `.devflow/codex-policy.yaml` 仍为 `disabled`。

## 禁止操作

- 不运行 `Codex Task`；
- 不运行 `Devflow Relay Health`；
- 不运行 `Devflow Secret Audit`；
- 不执行 Responses paid probe；
- 不重跑历史 Codex Workflow；
- 不读取或修改 Environment Secret；
- 不修改 PR #52 已交付的触发面实现。

## Gate

```yaml
implementation_files_changed: 0
codex_policy_after_closeout: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
pr_head_checks: PASS
post_merge_exact_main: PASS
```
