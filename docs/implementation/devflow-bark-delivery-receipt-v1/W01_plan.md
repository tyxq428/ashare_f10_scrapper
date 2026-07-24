# W01 计划：确定性 Bark Delivery Receipt 模型

## 目标

实现一个不读取Secret、不执行网络请求的确定性脚本，用受限参数生成并校验安全回执JSON。

## 文件

```text
scripts/devflow/bark_delivery_result.py
tests/test_devflow_bark_delivery_result.py
```

## CLI

```bash
python scripts/devflow/bark_delivery_result.py build \
  --validated-notification /tmp/validated-notification.json \
  --incident-run-id 123 \
  --incident-run-attempt 1 \
  --canonical-issue-number 99 \
  --delivery-status DELIVERED \
  --request-initiated true \
  --request-attempts 1 \
  --curl-exit-code 0 \
  --http-status 200 \
  --completed-at-utc 2026-07-24T00:00:00Z \
  --output /tmp/bark-delivery-result.json
```

## 规则

- task ID、notification type、marker和source字段来自已验证payload文件；
- `incident_run_id`、attempt和Issue number必须为正整数；
- `completed_at_utc`必须是秒精度UTC时间；
- 状态和值组合必须严格匹配；
- 输出固定声明：无自动重试、无响应正文/头、无Endpoint、无Secret；
- JSON字段集合固定，额外字段不允许；
- CLI只输出bounded状态，不打印回执全文。

## 测试

- `DELIVERED`有效组合；
- curl失败的`FAILED`；
- HTTP非2xx的`FAILED`；
- 配置缺失的SKIPPED；
- 非法状态组合拒绝；
- URL/Secret类字段不在输出；
- timestamp、marker、Run ID和Issue number校验；
- JSON round-trip与字段白名单。

## Gate

```yaml
python_compile: PASS_required
unit_tests: PASS_required
network_requests: 0
secret_reads: 0
```