# W00 计划：库存、事件合同与安全回执 Schema

## 输入

- `.github/workflows/devflow-incident.yml`；
- `.devflow/notification-channels.yaml`；
- `scripts/devflow/validate_notification_channels.py`；
- `scripts/devflow/validate_workflows.py`；
- `tests/test_devflow_bark_*.py`；
- 当前通知 Policy、Incident Runbook 和上一任务最终报告。

## 核验问题

1. Bark POST 的真实结果目前可在哪里观察；
2. 是否存在可下载、可机器验证的安全回执；
3. 哪些字段足够证明“请求被发起”与“服务端返回2xx”；
4. 如何保证回执不泄漏 Secret、Endpoint、响应正文或响应头；
5. 如何让回执上传和评论失败保持 fail-open；
6. 如何通过本任务自身的 canonical completion 做一次非 synthetic live验证。

## 产出

- `W00_result.md`；
- 完整回执 JSON Schema；
- 状态机和字段白名单；
- `W01_plan.md`。

## Gate

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
bark_requests: 0
secret_values_read: 0
```