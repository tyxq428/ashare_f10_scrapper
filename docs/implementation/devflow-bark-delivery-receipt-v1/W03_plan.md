# W03 计划：永久守卫、机器清单与操作文档

## 目标

把W02的回执行为变成机器可验证的长期合同，防止后续维护扩大Artifact范围、泄漏Endpoint/响应内容、增加重试或移除Issue索引。

## 机器清单

扩展 `.devflow/notification-channels.yaml` 的Bark配置：

```yaml
receipt:
  enabled: true
  artifact_name_prefix: bark-delivery-receipt-
  artifact_file: /tmp/bark-delivery-result.json
  retention_days: 14
  maximum_files: 1
  issue_index_enabled: true
  artifact_upload_fail_open: true
  issue_index_fail_open: true
  response_body_stored: false
  response_headers_stored: false
  endpoint_stored: false
  raw_error_stored: false
```

## Validator

`validate_notification_channels.py` 必须证明：

- 只有Incident引用回执生成器和评论渲染器；
- Incident只有一个Bark POST和一个回执Artifact上传位置；
- Artifact path精确为单一JSON文件；
- retention为14天；
- upload/comment均`continue-on-error`；
- Issue索引和Artifact marker存在；
- response/endpoint/Secret安全标记存在；
- Auto Recovery不监听或重试Artifact/Incident。

`validate_workflows.py` 必须把回执片段纳入Incident永久要求。

## 文档

更新：

- `docs/process/policies/notification-policy.md`；
- `docs/process/runbooks/handle-incident.md`。

内容包括：

- Artifact与canonical state的权威边界；
- 如何从Issue取得Incident Run和Artifact ID；
- 如何下载并运行`bark_delivery_result.py validate`；
- delivered/failed/skipped的解释；
- Artifact过期或缺失时不得推断Bark未发送；
- 禁止通过UI Re-run补发。

## 测试

- manifest/Workflow一致性；
- Artifact单文件与保留期；
- receipt scripts唯一使用者；
- upload/comment fail-open；
-响应/Endpoint/Secret排除；
- Validator负向fixture或文本变异检查。

## Gate

```yaml
workflow_validator: PASS_required
docs_validator: PASS_required
ruff: PASS_required
pytest: PASS_required
bark_requests: 0
secret_reads: 0
```