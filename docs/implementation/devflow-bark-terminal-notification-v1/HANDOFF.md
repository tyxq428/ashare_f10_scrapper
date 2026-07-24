# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00终态事件合同和现状库存已完成；
- W01通用事件校验、Bark JSON渲染和canonical完成转换扫描已实现；
- W02 Incident已泛化到任意登记任务，Issue marker去重和单次Bark Transport已实现；
- 10个本地测试、YAML解析、run block Bash语法和Python编译通过；
- Codex Policy保持 `disabled`；
- 未调用 Codex、Responses、Relay或 Bark；
- 未读取或配置任何 Secret。

## 当前阶段

```yaml
stage: W03
last_completed_stage: W02
next_action:
  - add_main_task_state_completion_producer
  - inject_task_id_into_auto_recovery_terminal_events
  - centralize_product_and_post_merge_failure_notification
  - add_notification_surface_validator
  - update_notification_policy_and_incident_runbook
```

## 不要执行

- 不监听所有 `workflow_run: completed`并直接通知；
- 不把 `BARK_PUSH_URL`写入仓库、Issue、PR、Artifact或日志；
- 不复用 `agent-runtime`；
- 不为 Bark失败触发 Auto Recovery；
- 不自动重试Bark；
- 不在配置完成前发送真实 Bark；
- 不调用或测试 Codex、Responses或历史模型 Workflow。

## 预期人工门槛

W03–W04实现和确定性Gate完成后，需要用户在GitHub UI创建/确认 `notification-runtime`并添加 `BARK_PUSH_URL`。Secret值不得通过聊天传递。