# 任务合同：Devflow Bark Terminal Notification v1

## 目标

在不改变现有 canonical state、自动恢复与有价值通知语义的前提下，为任务明确完成、明确中断、真实人工门槛和安全阻断增加一次性 Bark 手机推送通道。

Bark 只作为即时提醒渠道；`task_state.yaml` 和 canonical task-control Issue 继续作为权威状态与持久记录。

## 硬约束

```yaml
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
raw_workflow_run_notifications: forbidden
bark_requests_during_implementation: 0
bark_automatic_retries: 0
bark_requests_per_logical_notification_max: 1
```

## 允许通知的终态

```text
COMPLETED
INTERRUPTED
HUMAN_REQUIRED
SECURITY_BLOCKED
```

`QUEUED / RUNNING / RETRYING`、普通 Gate PASS、阶段完成、自动重试和确定性修复全部保持静默。

## 安全边界

- Bark Secret 使用独立 GitHub Environment `notification-runtime`；
- 不复用 `agent-runtime`，不读取或复制 Relay Secret；
- Bark URL/Device Key 不进入仓库、日志、Issue、PR、Artifact或 Job Summary；
- Bark 发送失败不得撤销任务终态、触发自动恢复或形成通知循环；
- GitHub UI Re-run 不得重复发送同一条 Bark；
- 所有第三方 Action继续固定完整 SHA。

## 完成定义

1. `devflow_notify` 事件合同可以按任意登记任务校验，不再硬编码单一 task ID；
2. `Devflow Incident` 继续维护 task-control Issue，并可在去重后投递一次 Bark；
3. 完成事件只在 canonical `DONE / COMPLETED / PASS` 与 post-merge PASS 后成立；
4. 中断类事件必须来自既有确定性分类或显式安全/人工决策；
5. 静态扫描和单元测试证明无 raw `workflow_run` 通知、无自动重试、无模型与 Responses耦合；
6. 人工配置 `notification-runtime` 与 `BARK_PUSH_URL` 后，可进行一次明确确认的 live test；
7. 完整 Test、真实 688521 E2E、exact-main 和最终状态收尾通过。