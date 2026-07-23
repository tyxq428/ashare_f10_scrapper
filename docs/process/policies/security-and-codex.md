# 安全、Codex Thin Worker 与自动恢复政策

## Secrets

中转站 URL、hostname、API Key 和模型 ID 全部视为 Secret，只能存入 GitHub Environment `agent-runtime`。首选名称：

```text
AGENT_RESPONSES_ENDPOINT
AGENT_API_KEY
AGENT_MODEL
```

为兼容已经存在的正式环境，Workflow 还可只读以下 Secret 名称别名，但不得把值复制到仓库：

```text
CODEX_RESPONSES_ENDPOINT / CODEX_ENDPOINT
CODEX_API_KEY / CODEX_TOKEN / OPENAI_API_KEY
CODEX_MODEL
```

不得进入仓库、Variables、日志、Issue、PR、Artifact、Failure Bundle 或异常正文。扫描完整值、去尾斜杠值、hostname、URL 编码、标准 Base64 和 Base64URL 编码变体。

## Environment 绑定边界

`agent-runtime` 必须直接声明在入口 Workflow 的普通 Secret-bearing Job 上：

```yaml
jobs:
  codex:
    environment:
      name: agent-runtime
      deployment: false
    permissions:
      contents: read
```

不得把 Secret-bearing Job 放进由本地 `workflow_call` 间接调用的 reusable workflow。正式运行已经证明：普通 Job 的 Environment presence 探针可读到三个 Secret，而旧 reusable workflow 边界中的同名表达式为空。为消除平台行为差异：

- `codex-task.yml` 直接拥有 Environment 和 Secret-bearing Job；
- 可复用单元是 `.github/actions/codex-thin-worker/action.yml` composite action；
- composite action 只接收显式 inputs，不直接读取 `secrets.*`；
- `Codex Task` 只接受显式 `workflow_dispatch`，不使用任务分支 Push 触发旧分支中的 Workflow 版本。

## 私有转发

Codex Action 只连接：

```text
http://127.0.0.1:8787/v1/responses
```

Runner 内无日志 Forwarder 从 Environment Secret 读取真实上游并标准化到 Responses endpoint。Forwarder 不记录 URL、Header、请求体、模型 ID 或原始上游错误。

## 权限分离

- Codex Job：`environment: agent-runtime`、`contents: read`、`persist-credentials: false`。
- Composite Codex Action：只接收当前 Job 的 Key、Model、Prompt 和输出路径 inputs；不拥有 GitHub 写权限。
- Publish Job：`contents: write`，不声明 Environment，不接收任何 Relay Secret。
- Product Gate、Auto Recovery 和 Post-Merge：不得声明 `agent-runtime` 或引用 Relay Secret。
- Job 间只传经过扫描的 Patch、Manifest、结构化结果和 Gate 摘要。
- Codex 控制分支中的 `.agent/current_task.yaml` 在产品分支提交前必须移除。

## Thin Worker 边界

- 一个明确目标；
- 显式允许路径和禁止路径；
- 每个 Task Generation 一次 Session；
- `effort: low`；
- 输出 Schema；
- 一个 Targeted Gate；
- 不做总规划、业务口径、Secret/Workflow 变更、长报告或无限修复；
- 越界修改立即 `SECURITY_BLOCKED`，不得提交或自动重试。

## Recovery Generation

自动恢复最多创建一个新的 Codex Recovery Generation。它必须：

- 从最新安全基线或失败产品分支创建；
- 继承原 `allowed_files`、`forbidden_patterns`、Gate 和风险等级；
- 记录 parent task/run 和 generation；
- 不扩大权限或上下文；
- 再失败时进入人工或阻断状态。

## 低风险自动合并

旧政策中的“禁止任何自动合并”改为更精确的边界：

- 中高风险任务仍禁止自动合并；
- `.github/**`、`docs/**`、`src/**`、Schema、Secrets、业务口径和不可逆变更禁止自动合并；
- 只有 `risk_class=low`、明确 `auto_merge=true`、允许文件不超过 5 个且 Scope/Secret/Targeted/Full Gate 全部通过时，Product Gate 才能受控合并；
- 合并冲突、权限或分支保护不允许强推，必须 `HUMAN_REQUIRED`；
- 自动合并后必须 exact-main Post-Merge，失败时按同一恢复预算处理。

## 触发安全

不支持：

- Fork PR 自动执行 Secret Job；
- `pull_request_target` 执行不可信代码；
- Issue/评论或自由文本中的任意 Shell；
- 未验证 Artifact 直接执行；
- 自动扩大修改范围；
- 无限 Codex 循环。

所有生产 Action 固定到完整 commit SHA；阶段之间使用显式 `workflow_dispatch` 或 `repository_dispatch`，Payload 仅含非 Secret 标识和经过验证的任务引用。
