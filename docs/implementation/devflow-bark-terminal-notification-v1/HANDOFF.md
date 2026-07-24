# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00终态事件合同和现状库存已完成；
- W01通用事件校验、Bark JSON渲染和canonical完成转换扫描已实现；
- 7个本地确定性单元测试和Python编译检查通过；
- Codex Policy保持 `disabled`；
- 未调用 Codex、Responses、Relay或 Bark；
- 未读取或配置任何 Secret。

## 当前阶段

```yaml
stage: W02
last_completed_stage: W01
next_action:
  - generalize_devflow_incident_for_registered_tasks
  - reuse_control_issue_marker_for_logical_deduplication
  - add_notification_runtime_bark_job
  - guard_github_reruns_with_run_attempt_1
  - add_static_transport_tests
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

W02–W04实现和确定性Gate完成后，需要用户在GitHub UI创建/确认 `notification-runtime`并添加 `BARK_PUSH_URL`。Secret值不得通过聊天传递。