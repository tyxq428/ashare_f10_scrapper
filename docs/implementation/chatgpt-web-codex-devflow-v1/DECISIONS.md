# Decisions

## D-001 — 使用 JSON-compatible YAML

Canonical `.yaml` 文件采用 JSON 语法（JSON 是 YAML 1.2 的子集），由 Python 标准库解析，避免为流程治理增加运行时依赖。

## D-002 — 状态不保存自引用 HEAD

使用 `base_sha_at_start` 和 `last_product_commit_sha` 祖先关系，不要求状态文件中的 SHA 等于包含该状态文件的提交 SHA。

## D-003 — Secret 与写权限分离

Codex Job 引用 `agent-runtime` Environment 且只有 `contents: read`。Publish Job 可写仓库但不引用 Environment。

## D-004 — Web Supervisor 控制 PR

Actions 负责验证 Patch 和 Push 工作分支；ChatGPT Web 创建/更新 PR、审查 Diff、决定合并。

## D-005 — 每个任务最多一个 Codex Session

失败后生成 Failure Bundle 并返回 ChatGPT Web，不自动启动第二个模型 Session。

## D-006 — 高价值通知

中间成功和审计 PASS 静默；只有完成、中断、人工和安全阻断通知用户。
