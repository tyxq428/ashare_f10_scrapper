# Runbook：Relay 健康检查

健康检查只在正式 Environment 首次启用、URL/Key/模型更新后，或出现认证/协议/流式错误时运行；普通 Codex 任务不重复握手。

1. 手工触发 `Devflow Relay Health`。
2. Job 在 `agent-runtime` Environment 中确认三个 Secret 非空，但不打印值。
3. 将 Base URL 私下标准化为 `/v1/responses`。
4. 发送一个极小 Streaming Responses 请求，显式 `reasoning.effort = none`，只期待固定短文本。
5. 只输出 HTTP 类别、是否 SSE、是否 completed 和输出是否匹配。
6. 对生成摘要执行 Secret 变体扫描；只上传安全摘要。
7. 成功保持静默。认证、协议或泄漏失败进入 `SECURITY_BLOCKED`/`HUMAN_REQUIRED`。
