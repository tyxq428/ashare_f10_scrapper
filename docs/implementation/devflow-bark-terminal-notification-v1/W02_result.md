# W02 结果：Incident泛化与Bark单次投递

```yaml
status: PASS
workflow: .github/workflows/devflow-incident.yml
generic_registered_tasks: true
canonical_issue_auto_resolution: true
logical_deduplication_marker: task_id+fingerprint+notification_type
bark_environment: notification-runtime
bark_secret: BARK_PUSH_URL
bark_run_attempt_guard: 1
bark_requests_per_logical_notification_max: 1
bark_automatic_retries: 0
bark_failure_changes_task_state: false
raw_workflow_run_notifications: 0
live_bark_requests: 0
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
```

## 已实现

- `Devflow Incident` 不再硬编码旧任务，使用 `notification_event.py`解析并校验任意登记任务；
- concurrency按payload task ID序列化，缺失task ID时使用安全的 unresolved队列；
- canonical state已有Issue编号时精确校验；没有编号时按精确标题查找或创建一个控制Issue；
- 多个同名Issue时Fail Closed；
- Issue评论只使用已裁剪、已验证字段；
- 复用 `devflow-root:<fingerprint>:<type>` marker阻止逻辑重复事件；
- marker写入后才允许Bark Job运行；
- Bark Job固定从 `main`重新校验payload并重新生成JSON；
- Bark只使用独立 `notification-runtime` 和 `BARK_PUSH_URL`；
- `github.run_attempt == 1`、`curl --retry 0`且只有一个POST位置；
- 响应正文丢弃，不上传HTTP Artifact；
- 缺少配置或请求失败时fail-open，canonical state和Issue保持权威；
- Auto Recovery未监听Incident或Bark Job。

## 确定性Gate

```text
PyYAML parse: PASS
bash -n for every run block: PASS
pytest -q tests/test_devflow_bark_notification.py tests/test_devflow_bark_workflow.py
..........                                                               [100%]
10 passed
python -m py_compile: PASS
```

本阶段未创建 `notification-runtime`，未读取Secret，也未发送真实Bark。