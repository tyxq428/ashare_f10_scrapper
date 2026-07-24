# 任务合同：Devflow Bark Delivery Receipt v1

## 目标

在现有任务级 Bark 终态通知基础上增加一个安全、可下载、可由 ChatGPT Web 核验的投递回执 Artifact，并用本任务自身的最终 `COMPLETED` 通知验证一次真实 Bark 请求是否被发起及服务端是否返回 HTTP 2xx。

## 已有基础

- 终态通知只接受 `COMPLETED / INTERRUPTED / HUMAN_REQUIRED / SECURITY_BLOCKED`；
- `Devflow Incident` 通过 canonical Issue marker 去重；
- Bark 使用独立 `notification-runtime` 和 `BARK_PUSH_URL`；
- 每条逻辑通知最多一个 HTTPS POST，`run_attempt=1`，无自动重试；
- Bark 失败为 fail-open，不改变 canonical task state。

## 新增范围

1. 生成不含 Secret、Endpoint、响应正文和响应头的 `bark-delivery-result.json`；
2. 无论 Bark 成功、失败或因配置缺失跳过，都输出稳定状态；
3. 使用固定名称前缀、有限保留期上传 Artifact；
4. 在 canonical task-control Issue 中追加安全回执索引，记录 Incident Run ID、Artifact ID 和投递结论；
5. 增加机器清单、静态 Validator 和单元测试；
6. 合并后以本任务的真实 `COMPLETED` generation 发起最多一次 Bark，并下载 Artifact 核验。

## 硬约束

```yaml
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_automatic_retries: 0
bark_live_requests_before_final_completion: 0
bark_live_requests_for_final_completion_max: 1
bark_secret_value_reads_by_chatgpt: 0
```

## 禁止

- 不读取、显示、复制、哈希或变换 `BARK_PUSH_URL`；
- 不保存 Bark 响应正文、响应头、DNS、IP、hostname 或 Endpoint 诊断；
- 不让 Artifact 失败改变任务终态；
- 不为 Bark 或 Artifact 上传失败触发 Auto Recovery；
- 不通过 GitHub UI Re-run 补发；
- 不创建永久或临时 synthetic Bark 测试 Workflow；
- 不调用 Codex、Responses、Relay Health、Secret Audit 或历史模型 Workflow。

## 完成定义

- 实现 PR 的完整 Test、State Consistency、Upgrade Compatibility 和真实 688521 E2E 通过；
- exact-main 验证通过且 Codex Policy 仍为 `disabled`；
- closeout 的 canonical DONE generation 触发一次真实终态通知；
- canonical Issue 出现回执索引；
- 回执 Artifact 可下载并通过 schema 校验；
- 回执明确区分 `DELIVERED / FAILED / SKIPPED_MISSING_CONFIGURATION`，并记录是否实际发起请求；
- Secret、Endpoint 和响应内容未进入仓库、Issue、日志或 Artifact。