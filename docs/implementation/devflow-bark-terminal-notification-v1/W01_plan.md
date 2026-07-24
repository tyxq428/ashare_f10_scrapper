# W01 计划：通用事件校验、Bark渲染与完成转换扫描

## 修改范围

```text
.devflow/notification-channels.yaml
scripts/devflow/notification_event.py
scripts/devflow/terminal_notification_scan.py
tests/test_devflow_bark_notification.py
```

## `notification_event.py`

职责：

1. 从 `ACTIVE_TASKS.yaml`解析显式 task ID；缺失 task ID时只允许“恰有一个非 DONE任务”的安全回退；
2. 验证通知类型、action、reason code、fingerprint、来源 Run和失败步骤；
3. 验证 state路径不能逃逸仓库且 state中的 task ID一致；
4. `COMPLETED` 必须满足严格 canonical DONE条件；
5. target URL只允许当前 GitHub仓库；
6. 输出裁剪后的 Issue字段、marker和 Bark JSON；
7. 不读取 Secret，不执行网络请求。

## `terminal_notification_scan.py`

职责：

- 比较 main push的 before/after SHA；
- 只检查发生变化的 `docs/implementation/*/task_state.yaml`；
- 仅当 notification generation增加、`last_type=COMPLETED`、`acknowledged=false`且严格 DONE条件成立时输出一个完成事件；
- 同 generation、非 DONE或已确认状态不产生事件；
- 输出给后续 Workflow dispatch使用的安全 JSON数组。

## 机器清单

`.devflow/notification-channels.yaml` 固化：

```yaml
canonical_issue: enabled
bark:
  environment: notification-runtime
  secret: BARK_PUSH_URL
  maximum_requests_per_notification: 1
  automatic_retry: false
```

## 测试

覆盖：

- 合法完成事件；
- COMPLETED与非 DONE state不一致时 Fail Closed；
- 非法 task ID、URL、类型、fingerprint；
- 缺 task ID且活动任务唯一/不唯一；
- Bark标题、级别、group和长度裁剪；
- state generation首次增加产生事件；
- 相同 generation、acknowledged或非 DONE保持静默；
- 全部测试使用临时目录和本地 Git仓库，不发送 HTTP请求。

## Gate

```yaml
ruff: PASS
pytest_bark_notification: PASS
network_requests: 0
secret_reads: 0
codex_calls: 0
responses_paid_probes: 0
```