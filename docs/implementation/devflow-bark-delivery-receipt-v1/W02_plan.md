# W02 计划：Incident Artifact 与 canonical Issue 回执索引

## 目标

把W01的确定性回执模型接入 `Devflow Incident`，使每个实际进入Bark Job的逻辑通知产生一份安全Artifact，并在canonical task-control Issue中留下可定位该Artifact的索引。

## Workflow变更

### Bark Transport输出

`Send one terminal Bark notification` 必须输出：

```yaml
delivery_status: DELIVERED|FAILED|SKIPPED_MISSING_CONFIGURATION
request_initiated: true|false
request_attempts: 0|1
curl_exit_code: integer|null
http_status: integer|null
```

Transport继续满足：

- HTTPS only；
- TLS 1.2 minimum；
- `--retry 0`；
- `--silent`且无`--show-error`；
- 响应正文写入 `/dev/null`；
- 失败Step为`continue-on-error`；
- 每条逻辑通知最多一个POST。

### 回执生成

在 `if: always()` 步骤调用：

```text
scripts/devflow/bark_delivery_result.py build
```

输入只来自：

- `/tmp/validated-notification.json`；
- GitHub Run ID/attempt；
- canonical Issue number；
- Transport安全输出；
- 秒精度UTC时间。

### Artifact上传

使用已固定SHA的 `actions/upload-artifact`：

```yaml
name: bark-delivery-receipt-${{ github.run_id }}
path: /tmp/bark-delivery-result.json
retention-days: 14
if-no-files-found: error
compression-level: 0
continue-on-error: true
```

### Issue回执索引

Artifact上传后，在同一canonical Issue追加安全评论：

- delivery status；
- request initiated/count；
- curl exit code；
- HTTP status；
- Incident Run URL；
- Artifact ID和URL；
- Artifact上传结果；
- 固定声明：无响应正文、响应头、Endpoint和Secret。

评论通过独立marker去重。评论失败为fail-open。

## 权限

Bark Job保持：

```yaml
contents: read
issues: write
```

不增加仓库写权限，不引用 `agent-runtime`。

## 测试

- 静态证明唯一Artifact上传位置；
- Artifact只包含单一JSON文件；
- 只有Incident可生成Bark回执；
- Issue索引不包含Endpoint/Secret/响应内容；
- 回执生成、上传、评论失败不触发Auto Recovery；
- GitHub rerun不重发或重复回执。

## Gate

```yaml
bark_requests: 0
synthetic_tests: 0
workflow_yaml_parse: PASS_required
static_validator: PASS_required
unit_tests: PASS_required
```