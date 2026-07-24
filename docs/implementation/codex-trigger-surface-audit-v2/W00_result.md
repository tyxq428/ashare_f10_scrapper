# W00 结果：全仓与历史执行面审计

```yaml
status: PASS
main_codex_policy: disabled
main_direct_model_actions: 0
main_automatic_codex_dispatches: 0
main_codex_failed_job_retries: 0
new_risk_historical_workflow_rerun: CONFIRMED
new_risk_legacy_task_branch_descriptor: CONFIRMED
new_risk_relay_paid_probe_auto_retry: CONFIRMED
codex_calls: 0
responses_paid_probes: 0
```

## 关键证据

历史 Run `30020008656` 使用旧版 `Codex Task` Workflow，并把输入分支解析为：

```text
task/codex-devflow-state-consistency-30019938651-recovery-g1
```

该分支目前仍存在 `.agent/current_task.yaml`。虽然其 Composite Action 已被早期熔断补丁覆盖，但其他历史任务分支不能依靠人工逐个确认，必须建立自动枚举和隔离机制。

`Devflow Relay Health` 会向 Responses endpoint 发送请求，因此属于付费探针；它不能继续使用通用 Auto Recovery 的 `rerun-failed-jobs` 路径。
