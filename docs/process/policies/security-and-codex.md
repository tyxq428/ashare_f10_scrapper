# 安全与 Codex Thin Worker 政策

## Secrets

中转站 URL、hostname、API Key 和模型 ID 全部视为 Secret，只能存入 GitHub Environment `agent-runtime`：

```text
AGENT_RESPONSES_ENDPOINT
AGENT_API_KEY
AGENT_MODEL
```

不得进入仓库、Variables、日志、Issue、PR、Artifact 或失败正文。扫描完整值、去尾斜杠值、hostname、URL 编码、标准/Base64URL 编码变体。

## 私有转发

Codex Action 只连接：

```text
http://127.0.0.1:8787/v1/responses
```

Runner 内无日志 Forwarder 从 Environment Secret 读取真实上游，标准化到 Responses endpoint。Forwarder 不记录 URL、Header、请求体或原始上游错误。

## 权限分离

- Codex Job：`environment: agent-runtime`、`contents: read`、`persist-credentials: false`。
- Publish Job：`contents: write`，不声明 Environment，不接收任何 Relay Secret。
- Job 间只传经过扫描的 Patch、Manifest、结构化结果和 Gate 摘要。

## Thin Worker 边界

- 一个明确目标；
- 显式允许路径和禁止路径；
- 一次 Session；
- `effort: low`；
- 输出 Schema；
- 最多一个 G1 profile；
- 不做总规划、业务口径、PR、合并、长报告或无限修复；
- 越界修改立即阻断，不提交。

## 触发安全

不支持 Fork PR、`pull_request_target`、Issue/评论中的任意命令、自动第二 Session、自动合并或不受信任 Artifact 执行。生产 Action 固定到完整 commit SHA。
