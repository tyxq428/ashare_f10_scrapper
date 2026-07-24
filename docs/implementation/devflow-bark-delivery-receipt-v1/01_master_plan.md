# 总计划：Devflow Bark Delivery Receipt v1

## W00｜库存、合同与回执 Schema

- 对账当前 `Devflow Incident`、通知清单、Validator 和测试；
- 明确现有缺口：只能从 Job Summary 判断 Bark，缺少可下载的稳定机器回执；
- 固化回执字段、状态机、Secret 排除规则和 live 验证方式。

## W01｜确定性回执模型

新增 `scripts/devflow/bark_delivery_result.py`：

- 根据受限 CLI 参数生成 `bark-delivery-result.json`；
- 校验 task ID、notification type、marker、Run ID、HTTP status 和 request count；
- 支持 `DELIVERED / FAILED / SKIPPED_MISSING_CONFIGURATION`；
- 强制 `response_body_stored=false`、`response_headers_stored=false`、`endpoint_logged=false`、`automatic_retry=false`；
- 不读取 Secret，不执行网络请求；
- 增加完整单元测试。

## W02｜Incident Artifact 与 Issue 回执索引

- Bark Transport 捕获安全的 `curl_exit_code` 和 HTTP status；
- 在 `if: always()` 步骤生成回执 JSON；
- 使用固定 SHA 的 `actions/upload-artifact` 上传唯一文件；
- 通过 Artifact action 输出的 ID/URL，在 canonical Issue 追加安全回执索引；
- Bark、回执生成、Artifact 上传或回执评论失败均不改变 canonical task state；
- 不把响应正文、响应头、Endpoint 或 Secret 放入任何输出。

## W03｜永久守卫、文档与 PR Gate

- 扩展 `.devflow/notification-channels.yaml`；
- 扩展 `validate_notification_channels.py` 和 `validate_workflows.py`；
- 扩展静态 Workflow 测试；
- 更新通知 Policy 和 Incident Runbook；
- 创建实现 PR；
- 运行 Upgrade Compatibility、Test、State Consistency 和真实 688521 E2E。

## W04｜实现合并、原子 closeout 与真实 Bark 验证

1. 合并实现 PR；
2. 验证 exact-main 源码和确定性 Gate；
3. 使用独立 closeout PR 原子写入 DONE state、FINAL_REPORT、STATUS、HANDOFF 和 ACTIVE_TASKS；
4. closeout 合并后等待 main 的 State Consistency PASS；
5. 本任务新 `COMPLETED` generation 触发 `Devflow Incident`；
6. 等待最多一次 Bark POST；
7. 从 canonical Issue 读取 Incident Run ID 和 Artifact ID；
8. 下载并校验 `bark-delivery-result.json`；
9. 最终报告记录真实结果，不因 Bark 失败撤销 DONE。

## 回执状态

```yaml
DELIVERED:
  request_initiated: true
  request_attempts: 1
  curl_exit_code: 0
  http_status: 2xx

FAILED:
  request_initiated: true
  request_attempts: 1
  curl_exit_code: nonzero_or_http_non_2xx
  http_status: integer_or_null

SKIPPED_MISSING_CONFIGURATION:
  request_initiated: false
  request_attempts: 0
  curl_exit_code: null
  http_status: null
```

## Artifact 安全合同

Artifact 只允许包含：

- schema/version；
- task、notification、marker；
- Incident/source Run ID；
- canonical Issue number；
- delivery status；
- request initiated/count；
- safe numeric curl exit code和HTTP status；
- UTC时间；
-固定安全布尔值。

不得包含 Secret、URL、hostname、IP、响应正文、响应头、Bark返回消息、异常原文或环境快照。