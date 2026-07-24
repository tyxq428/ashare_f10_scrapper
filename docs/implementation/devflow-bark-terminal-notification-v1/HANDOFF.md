# Handoff：Devflow Bark Terminal Notification v1

## 最终检查点

- W00–W05 已完成并有计划、结果和最终报告；
- Incident 已泛化到任意登记任务，canonical Issue marker 去重和单次 Bark Transport 已实现；
- canonical 完成事件只在 State Consistency 全部 Gate PASS 后产生；
- 通知扫描、dispatch 和 Bark 发送失败均为 fail-open，不改变 canonical 任务结果，也不触发 Auto Recovery；
- 失败类终态由 Auto Recovery 集中分类，Product Gate 和 Post Merge 不再重复通知；
- 通知机器清单、永久 Validator、策略和 Runbook 已完成；
- 精确实现 head `e5a3678057640a426a941f609bbe0f14eace1011` 的四个确定性 Gate 全部 PASS；
- PR #54 已合并，Merge SHA 为 `4d782d8328b2e106708855d643e8e367c0cff73d`；
- 用户已完成 `notification-runtime` 平台配置并在 GitHub UI 添加 `BARK_PUSH_URL`；
- Secret 值未被读取、显示、复制到聊天、仓库、PR、Issue、日志或 Artifact；
- Codex Policy 保持 `disabled`；
- Codex、Responses、Relay 和历史模型 Workflow 调用均为 0。

## 最终状态

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
stage: W05
last_completed_stage: W05
branch: main
pull_request: 54
implementation_merge_sha: 4d782d8328b2e106708855d643e8e367c0cff73d
next_action: none
human_required: false
```

## 平台状态

```yaml
notification_runtime:
  required_reviewers: none
  administrator_bypass: disabled
  deployment_branches:
    - main
  BARK_PUSH_URL: configured_in_GitHub_UI
  secret_value_read_or_displayed: false
```

## 后续运行语义

每当未来任务达到有价值终态时：

```text
terminal decision
→ devflow_notify
→ canonical task-control Issue marker
→ at most one Bark POST
```

`COMPLETED` 必须先通过 canonical DONE 和 State Consistency；`INTERRUPTED / HUMAN_REQUIRED / SECURITY_BLOCKED` 必须先经过确定性分类或显式终止路径。

## 不要执行

- 不监听所有 `workflow_run: completed` 并直接通知；
- 不读取、输出或复制 `BARK_PUSH_URL`；
- 不复用 `agent-runtime`；
- 不为通知失败触发 Auto Recovery；
- 不自动重试 Bark；
- 不通过 GitHub UI Re-run 补发 Bark；
- 不把 Bark 作为状态源；
- 不调用或测试 Codex、Responses、Relay 或历史模型 Workflow。

## 本任务真实完成通知

本 closeout 与 `ACTIVE_TASKS.yaml` 原子进入 `main` 后，State Consistency PASS 将处理 notification generation 3，建立或更新 `[TASK CONTROL] devflow-bark-terminal-notification-v1`，并尝试最多一次 Bark。无论 Bark HTTP 结果如何，canonical state 和 Issue 都是权威结果，任务不再需要恢复。
