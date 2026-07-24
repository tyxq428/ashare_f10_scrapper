# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- 已从最新 `main` 创建 `feature/devflow-bark-terminal-notification-v1`；
- 任务合同、总计划、W00计划和 canonical state已持久化；
- Codex Policy保持 `disabled`；
- 未调用 Codex、Responses、Relay或 Bark；
- 未读取或配置任何 Secret。

## 当前阶段

```yaml
stage: W00
next_action:
  - inventory_devflow_notify_producers
  - define_generic_terminal_event_contract
  - prove_raw_workflow_failures_remain_silent
  - write_W00_result
  - persist_W01_plan_before_implementation
```

## 不要执行

- 不监听所有 `workflow_run: completed`并直接通知；
- 不把 `BARK_PUSH_URL`写入仓库、Issue、PR或日志；
- 不复用 `agent-runtime`；
- 不为 Bark失败触发 Auto Recovery；
- 不在配置完成前发送真实 Bark；
- 不调用或测试 Codex、Responses或历史模型 Workflow。

## 预期人工门槛

实现与确定性 Gate完成后，需要用户在 GitHub UI创建/确认 `notification-runtime`并添加 `BARK_PUSH_URL`。Secret值不得通过聊天传递。