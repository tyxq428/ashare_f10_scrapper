# W04 计划：精确PR Head确定性验证与平台交接准备

## 目标

在不读取Bark Secret、不发送真实Bark且Codex Policy保持disabled的前提下，验证完整通知链路的代码、状态、Workflow和产品回归，并把唯一剩余的平台配置转入真实人工门槛。

## 精确Head Gate

对最终PR head运行并要求全部PASS：

1. Devflow Upgrade Compatibility；
2. Test；
3. Devflow State Consistency；
4. 真实 E2E 688521。

State Consistency必须覆盖：

```text
validate_state.py --all-active
validate_codex_entrypoints.py
validate_workflows.py
validate_docs.py
ruff check scripts/devflow tests/test_devflow*.py
pytest -q tests/test_devflow*.py
```

## 静态安全验收

```yaml
raw_workflow_run_direct_notifications: 0
notification_runtime_workflows:
  - .github/workflows/devflow-incident.yml
bark_secret_workflows:
  - .github/workflows/devflow-incident.yml
bark_http_post_locations: 1
bark_requests_per_logical_notification_max: 1
bark_automatic_retries: 0
github_rerun_resend: false
completion_source: Devflow State Consistency
completion_delivery_fail_open: true
notification_failure_auto_recovery: 0
agent_runtime_references_in_bark_path: 0
codex_or_responses_references_in_bark_path: 0
```

## 运行时非动作

本阶段禁止：

- 创建或读取 `notification-runtime` Secret；
- 发送真实Bark；
- 运行Incident live payload；
- 运行Relay Health、Secret Audit或Responses探针；
- 运行Codex Task或任何历史Codex Workflow；
- 通过重跑测试通知幂等性。

幂等性和失败语义只通过本地临时Git仓库、静态Workflow检查和单元测试证明。

## 通过后的状态

若全部确定性Gate通过：

- 写 `W04_result.md`；
- 持久化 `W05_plan.md`；
- 状态转为 `WAITING_HUMAN / BLOCKED`；
- 唯一人工动作是GitHub UI配置 `notification-runtime` 和 `BARK_PUSH_URL`；
- PR保持Draft且不合并，避免本任务完成事件在Secret未配置时被Issue marker永久去重。

## Gate预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
bark_requests: 0
live_notification_dispatches: 0
```