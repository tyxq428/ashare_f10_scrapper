# W00 结果：现状库存与安全回执合同

```yaml
status: PASS
current_bark_post_locations: 1
current_bark_automatic_retries: 0
current_response_body_storage: 0
current_endpoint_diagnostics: 0
current_delivery_receipt_artifacts: 0
current_machine_readable_delivery_status: 0
current_issue_receipt_index: 0
bark_requests_during_W00: 0
secret_values_read: 0
```

## 现状

当前 `Devflow Incident` 已经安全执行最多一次Bark POST，并在Job Summary写入成功、失败或配置缺失的文本标记；但这些标记不是稳定Artifact，ChatGPT Web无法通过现有Connector可靠取得push事件的Incident Run与Transport结论。

因此真正缺口不是“是否能发送”，而是：

1. 缺少稳定机器回执；
2. 缺少Incident Run和Artifact ID的持久索引；
3. 无法在不依赖Gmail或人工截图的情况下核验真实Bark请求；
4. 无法区分“请求已发起但失败”和“因配置缺失未发起”。

## 回执Schema

```json
{
  "schema_version": 1,
  "task_id": "example-task",
  "notification_type": "COMPLETED",
  "marker": "devflow-root:...:COMPLETED",
  "incident_run_id": 123,
  "incident_run_attempt": 1,
  "source_workflow": "Devflow State Consistency",
  "source_run_id": 122,
  "canonical_issue_number": 99,
  "delivery_status": "DELIVERED",
  "request_initiated": true,
  "request_attempts": 1,
  "curl_exit_code": 0,
  "http_status": 200,
  "automatic_retry": false,
  "response_body_stored": false,
  "response_headers_stored": false,
  "endpoint_logged": false,
  "secret_value_stored": false,
  "completed_at_utc": "2026-07-24T00:00:00Z"
}
```

## 状态约束

- `DELIVERED`：请求1次、curl exit 0、HTTP 200–299；
- `FAILED`：请求1次，curl失败或HTTP非2xx；
- `SKIPPED_MISSING_CONFIGURATION`：请求0次，无curl和HTTP状态；
- 所有状态均固定 `automatic_retry=false`；
- 回执只能记录数值和白名单元数据；
- 禁止任何URL、hostname、IP、响应正文、响应头、异常原文或Secret派生值。

## Artifact与Issue索引

- Artifact名称前缀：`bark-delivery-receipt-`；
- 文件：单一 `bark-delivery-result.json`；
- 保留期：14天；
- canonical Issue回执评论只记录安全字段、Incident Run URL、Artifact ID和Artifact URL；
- Artifact或评论失败为fail-open，不重试Bark，不改变task state。

## 验收

现状缺口和实现边界已明确。W01可以开始实现确定性回执生成器和单元测试。