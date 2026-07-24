# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00–W04 已完成并有计划/结果文档；
- Incident 已泛化到任意登记任务，canonical Issue marker 去重和单次 Bark Transport 已实现；
- canonical 完成事件只在 State Consistency 全部 Gate PASS 后产生；
- 通知扫描、dispatch 和 Bark 发送失败均为 fail-open，不改变 canonical 任务结果，也不触发 Auto Recovery；
- 失败类终态由 Auto Recovery 集中分类，Product Gate 和 Post Merge 不再重复通知；
- 通知机器清单、永久 Validator、策略和 Runbook 已完成；
- 精确 PR head `16bb730900412d05adf9e634b4526629975d0f4a` 的四个确定性 Gate 全部 PASS；
- 用户已完成 `notification-runtime` 平台配置并在 GitHub UI 添加 `BARK_PUSH_URL`；
- Secret 值未被读取、显示、复制到聊天、仓库、PR、Issue、日志或 Artifact；
- Draft PR #54 保持开放，等待恢复后的精确 head Gate；
- Codex Policy 保持 `disabled`；
- Codex、Responses、Relay、历史模型 Workflow 和真实 Bark调用仍为 0。

## 已确认的平台状态

```yaml
notification_runtime:
  required_reviewers: none
  administrator_bypass: disabled
  deployment_branches:
    - main
  BARK_PUSH_URL: configured_in_GitHub_UI
  secret_value_read_or_displayed: false
```

## 当前状态

```yaml
status: VERIFYING
execution_status: RUNNING
stage: W05
last_completed_stage: W04
pull_request: 54
next_action:
  - mark_PR54_ready
  - wait_for_resumed_exact_head_checks
  - merge_PR54
  - wait_for_exact_main_checks
  - write_W05_result_and_FINAL_REPORT
  - update_canonical_state_to_DONE
  - observe_single_real_completion_Bark_delivery
```

## 不要执行

- 不监听所有 `workflow_run: completed` 并直接通知；
- 不读取、输出或复制 `BARK_PUSH_URL`；
- 不复用 `agent-runtime`；
- 不为通知失败触发 Auto Recovery；
- 不自动重试 Bark；
- 不创建 synthetic 测试 Workflow；
- 不通过 GitHub UI Re-run 补发 Bark；
- 不调用或测试 Codex、Responses、Relay 或历史模型 Workflow。

## 真实验证

PR #54 合并和 exact-main Gate 完成后，任务将更新为新的 canonical DONE generation。随后 State Consistency PASS 触发唯一真实 `COMPLETED` 事件、canonical Issue 和最多一条 Bark。Bark HTTP 失败仍为 fail-open，不撤销 DONE。
