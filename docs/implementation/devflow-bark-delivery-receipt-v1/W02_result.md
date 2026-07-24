# W02 结果：Incident Artifact 与 canonical Issue 回执索引

```yaml
status: PASS
verified_head_sha: 48c526ed439c261a4ccd4accb2a21e08f8012ba9
upgrade_compatibility: PASS:30093003450
test: PASS:30093003437
state_consistency: PASS:30093003436
e2e_688521: PASS:30093003398
bark_requests: 0
secret_reads: 0
```

## Transport安全输出

`Send one terminal Bark notification` 现在在不输出Endpoint或原始错误的前提下生成：

- `delivery_status`；
- `request_initiated`；
- `request_attempts`；
- `curl_exit_code`；
- `http_status`。

Transport仍只有一个HTTPS POST位置，TLS 1.2、`--retry 0`、响应正文 `/dev/null`、无`--show-error`，失败Step保持`continue-on-error`。

## Artifact

每个实际进入Bark Job的新逻辑通知都会尝试生成并上传：

```text
bark-delivery-receipt-<task-id>-<incident-run-id>
└── bark-delivery-result.json
```

约束：

```yaml
retention_days: 14
compression_level: 0
maximum_files: 1
upload_failure: FAIL_OPEN
```

## canonical Issue索引

新增确定性 `bark_delivery_receipt_comment.py`：

- 只接受当前仓库、精确Incident Run和精确Artifact ID的GitHub URL；
- 记录安全Transport字段和Artifact索引；
- 不记录Secret、Bark URL、Endpoint、响应正文、响应头或原始错误；
- 使用独立marker去重；
- 评论失败保持fail-open。

## 失败语义

Bark、回执生成、Artifact上传和Issue回执索引四层独立记录。任何观察层失败均不会：

- 撤销canonical DONE；
- 改写task state；
- 触发Auto Recovery；
- 自动重试Bark；
- 通过UI Re-run补发。

## Gate

四个确定性Gate在精确集成head全部通过，且本阶段真实Bark请求数保持0。