# W08 计划：最终收尾、状态关闭与一次完成通知

## 目标

在真实低风险薄切片完成 exact-main Post-Merge 后，自动完成任务状态和文档收尾，并只发送一次最终完成通知。

## 自动收尾内容

- `task_state.yaml` 更新为 `DONE / COMPLETED / PASS`；
- `post_merge.status=PASS`，保存产品 Merge SHA 与 Run ID；
- `ACTIVE_TASKS.yaml` 将任务标记为 `DONE`；
- 生成或更新 W05–W08 结果文档；
- 生成 `FINAL_REPORT.md`；
- 重新生成 `STATUS.md` 与 `HANDOFF.md`；
- 对完成态执行 State Consistency 和 devflow tests；
- 将收尾文档提交到最新 `main`；
- 通过 canonical Issue #32 发送一次 `[TASK][COMPLETED]` 并关闭 Issue。

## 通知规则

- 中间 PASS、自动重试、Codex recovery generation、Product Gate 和普通 Push 全部静默；
- `/ack` 只表示已看到，不触发修复或继续；
- 只有真正的 `HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED` 才在完成前通知；
- 完成通知必须在 exact-main Post-Merge、状态一致性和最终文档验收全部通过后发送。

## 完成标准

```yaml
status: DONE
execution_status: COMPLETED
research_acceptance_status: PASS
post_merge: PASS
human_intervention_required: false
control_issue: closed completed
```
