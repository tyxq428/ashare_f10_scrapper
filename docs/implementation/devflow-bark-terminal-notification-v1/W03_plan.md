# W03 计划：终态生产者接线与永久静态守卫

## 修改范围

```text
.github/workflows/devflow-auto-recovery.yml
.github/workflows/devflow-product-gate.yml
.github/workflows/devflow-post-merge.yml
.github/workflows/devflow-terminal-state-notify.yml
scripts/devflow/validate_workflows.py
tests/test_devflow_bark_notification.py
tests/test_devflow_bark_workflow.py
docs/process/policies/notification-policy.md
docs/process/runbooks/handle-incident.md
docs/process/README.md
```

## 完成事件生产

新增 `Devflow Terminal State Notification`：

- 仅监听 `main` 上 `docs/implementation/*/task_state.yaml` 的 push；
- checkout精确 push SHA且完整历史；
- 使用 `terminal_notification_scan.py`比较 before/after；
- 只有新的严格 DONE generation产生 `COMPLETED`；
- 每个事件通过 `repository_dispatch: devflow_notify`进入Incident；
- 不直接读取Bark Secret，不直接发送HTTP；
- Workflow重跑产生相同marker，由Incident去重。

## 中断事件生产

- Auto Recovery在终态分类后使用 `notification_event.py resolve-task`解析唯一活动任务；
- dispatch前显式写入 `task_id`；
- 多活动任务或无安全解析时Fail Closed；
- Product Gate Full Gate失败和Post Merge失败不再直接发通知，统一交给Auto Recovery分类，避免重复；
- Product Gate的成功但禁止自动合并仍直接产生 `HUMAN_REQUIRED`，并显式携带task ID。

## Validator

永久验证：

1. 只有Incident引用 `notification-runtime` 和 `${{ secrets.BARK_PUSH_URL }}`；
2. Incident只有一个Bark POST位置；
3. `run_attempt == 1`、`--retry 0`、fail-open和响应丢弃均存在；
4. Incident与Terminal State Workflow均不监听 raw `workflow_run`；
5. Terminal State Workflow只监听main state路径；
6. Auto Recovery不监听Incident/Bark，且终态payload注入task ID；
7. Bark链路不引用 `agent-runtime`、AGENT Secret、Codex Action、Responses或Forwarder；
8. notification channel机器清单与实际Workflow一致。

## 文档

更新通知政策和Incident Runbook，明确：

- canonical Issue是持久记录，Bark是即时辅助通道；
- Bark采用at-most-once；
- 配置/网络失败不改变任务终态；
- 不在聊天、Issue或日志中传递Bark URL；
- `/ack`不触发任何执行。

## Gate

```yaml
completion_transition_tests: PASS
workflow_policy_tests: PASS
workflow_validator: PASS
duplicate_failure_producers: 0
raw_workflow_run_direct_notifications: 0
bark_secret_locations: 1
bark_post_locations: 1
live_bark_requests: 0
codex_calls: 0
responses_paid_probes: 0
```