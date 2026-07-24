# W02 计划：Incident泛化与Bark单次投递

## 修改范围

```text
.github/workflows/devflow-incident.yml
tests/test_devflow_bark_notification.py
```

## Incident准备阶段

1. 仍只监听 `repository_dispatch: devflow_notify`；
2. 从 `github.event.client_payload` 写入本地临时文件；
3. 使用 `notification_event.py prepare` 校验登记任务、canonical state和事件字段；
4. 动态解析或创建精确标题的 `[TASK CONTROL] <task-id>` Issue；
5. 以 `task_id + fingerprint + notification_type` marker去重；
6. marker已存在时设置 `should_push=false`并静默结束；
7. 首次事件写入裁剪后的 Issue评论，`COMPLETED` 时关闭控制 Issue。

## Bark阶段

```yaml
needs: valuable-notification
condition:
  should_push: true
  github.run_attempt: 1
environment: notification-runtime
permissions:
  contents: read
```

Bark Job重新从可信 `main` checkout并重新校验同一 payload，生成 `/tmp/bark-message.json`。发送规则：

- Secret只从 `${{ secrets.BARK_PUSH_URL }}`读取；
- `set +x`且立即 `::add-mask::`完整值；
- 只执行一次 `curl POST`；
- `connect-timeout=10`、`max-time=20`；
- 不输出响应正文、不上传HTTP Artifact；
- Secret缺失或请求失败只写固定安全摘要；
- Bark结果不改变canonical任务状态，不触发Auto Recovery；
- GitHub UI Re-run因 `run_attempt != 1`无法再次发送。

## Issue解析策略

- canonical state已有正整数 `control_issue_number`时，校验其标题；
- 否则通过 GitHub API查询当前仓库全部非PR Issue的精确标题；
- 0个匹配时创建一个控制 Issue；
- 多于1个匹配时 Fail Closed，防止写入错误目标；
- 创建/解析 Issue不修改task state中的编号，避免Incident Workflow写仓库。

## Gate

```yaml
payload_validation: PASS
generic_task_resolution: PASS
issue_marker_deduplication: PASS
bark_run_attempt_guard: PASS
bark_request_locations: 1
bark_automatic_retry: 0
raw_workflow_run_notification: 0
agent_runtime_references: 0
codex_or_responses_references: 0
live_bark_requests: 0
```

实现后补充静态测试，证明Bark Job失败是fail-open且不会进入自动恢复监听范围。