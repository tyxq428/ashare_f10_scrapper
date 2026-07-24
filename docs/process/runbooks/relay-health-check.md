# Runbook：Relay 健康检查

## 默认模式：零请求配置检查

普通检查只验证 `agent-runtime` 中 Endpoint、Key 和 Model 的存在性与 Endpoint 形状，不发送 Responses 请求：

1. 手工触发 `Devflow Relay Health`；
2. 保持 `mode=configuration_only`；
3. `confirm_paid_probe` 必须为空；
4. Workflow 在 Environment 中注册 Mask；
5. 运行 `runtime_preflight.py`；
6. Job Summary 必须包含：

```text
RELAY_HEALTH_MODE=CONFIGURATION_ONLY_ZERO_REQUEST
RESPONSES_REQUESTS_SENT=0
```

该模式不验证余额、认证、模型可用性或流式协议，只验证配置形状。

## 付费模式：一次显式 Responses 探针

只在以下情况考虑：

- 正式 Environment 首次启用；
- URL、Key 或模型刚更新；
- 已出现明确认证、协议或流式错误；
- 用户主动要求验证中转链路。

执行步骤：

1. 由 `tyxq428` 手工触发；
2. 选择 `mode=paid_responses_probe`；
3. 输入精确确认短语：

```text
I_ACCEPT_ONE_PAID_RESPONSES_PROBE
```

4. 填写非空 `purpose`；
5. Workflow先运行零请求配置检查；
6. 仅发送一个极小 Streaming Responses请求；
7. 只期待固定短文本，最多 32 输出 Token；
8. 只输出 HTTP类别、SSE、completed和固定输出匹配；
9. 对摘要执行 Secret扫描。

## 不可自动重试

`Devflow Relay Health` 不在 Auto Recovery监听列表中。无论失败发生在 Checkout、超时、网络、Artifact或请求之后，都不得使用 `rerun-failed-jobs` 自动重跑。

再次执行付费探针必须重新手工触发、重新输入确认短语和目的。

## 失败处理

- 配置缺失：`HUMAN_REQUIRED`，修正 Environment；
- 401/403：检查 Key；
- 404：检查 Responses Endpoint；
- 429：检查余额、额度或限流；
- 5xx/传输/协议：记录一次失败并停止，不自动重试；
- Secret Audit失败：`SECURITY_BLOCKED`。
