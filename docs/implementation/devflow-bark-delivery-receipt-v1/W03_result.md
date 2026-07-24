# W03 结果：永久守卫、机器清单与操作文档

```yaml
status: PASS
verified_head_sha: 1c3e1eca154df833a9cd1724dc4ae036af1b29cc
upgrade_compatibility: PASS:30093489300
test: PASS:30093489267
state_consistency: PASS:30093489321
e2e_688521: PASS:30093489286
bark_requests: 0
secret_reads: 0
```

## 机器清单

`.devflow/notification-channels.yaml` 现在声明：

- 回执生成器和Issue评论渲染器；
- Artifact名称前缀和单一JSON路径；
- 14天保留期；
- 最大文件数1；
- Artifact上传和Issue索引均fail-open；
- 响应正文、响应头、Endpoint、raw error和Secret均不保存。

## 永久Validator

`validate_notification_channels.py` 现在证明：

- `notification-runtime`、`BARK_PUSH_URL` 和回执脚本只被 `Devflow Incident` 使用；
- Incident恰好有一个Bark POST和一个Artifact上传位置；
- Artifact只上传 `/tmp/bark-delivery-result.json`；
- upload-artifact固定到完整SHA；
- retention、compression和缺文件行为固定；
- 回执build/validate和Issue renderer各出现一次；
- upload/comment/receipt失败均有fail-open标记；
- State Consistency和Auto Recovery不读取Secret、不生成回执、不重试Bark。

`validate_workflows.py` 已经把专用通知Validator的错误并入总Workflow Gate，因此没有复制同一套细节规则。

## 测试

静态Workflow测试新增：

- Artifact单文件、保留期和固定Action SHA；
- receipt builder/comment renderer；
- upload和Issue索引fail-open；
- manifest summary中的唯一使用者、上传次数、retention和Issue索引。

## 文档

通知Policy和Incident Runbook现在说明：

- 回执只是Transport观察证据；
- delivered/failed/skipped的严格语义；
- 如何从Issue取得Incident Run和Artifact ID；
- 如何下载并离线validate；
- Artifact过期或缺失不能证明请求未发起；
- 禁止UI Re-run补发。

## Gate结论

四个Gate在精确head全部PASS。实现、Validator和文档完整，且真实Bark请求仍为0。