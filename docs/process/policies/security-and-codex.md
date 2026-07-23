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

不得把 Secret-bearing Job 放进由本地 `workflow_call` 间接调用的 reusable workflow。正式运行已证明普通 Job 可读取 Environment Secrets，而旧 reusable workflow 边界中的同名表达式为空：

- `codex-task.yml` 直接拥有 Environment 和 Secret-bearing Job；
- 可复用单元是 `.github/actions/codex-thin-worker/action.yml` composite action；
- composite action 只接收显式 inputs，不读取 `secrets.*`；
- `Codex Task` 只接受显式 `workflow_dispatch`，不使用任务分支 Push 触发旧 Workflow 版本。

## 可信 Bot 授权

自动接力由仓库自身 `github-actions[bot]` 发起。官方 Codex Action 必须显式配置：

```yaml
allow-bots: "true"
allow-bot-users: github-actions[bot]
```

同时保留入口双重约束：

- `github.actor` 只能是仓库所有者或 `github-actions[bot]`；
- 输入只能是 `task/codex-*` 可信控制分支，并由 Task Descriptor 校验。

禁止任意用户/Bot 通配符、Issue 评论直接触发 Secret Job或外部 Fork 内容。

## 私有转发

Codex Action 只连接：

```text
http://127.0.0.1:8787/v1/responses
```

Runner 内无日志 Forwarder 从 Environment Secret 读取真实上游。Forwarder 不记录 URL、Header、请求体、模型 ID 或原始上游错误。

## XHigh 与版本化 Descriptor

生产 Composite Action 固定：

```yaml
effort: xhigh
```

- schema-v2 Task Descriptor 必须显式 `reasoning_effort: xhigh`；
- schema-v2 必须显式 Context Budget；
- schema-v1 `low` 只用于读取历史元数据，`effective_reasoning_effort` 仍为 XHigh；
- Recovery Generation 使用当前 schema-v2 和 XHigh；
- 任何执行器、文档或模板回退到 Low 都由静态检查阻断；
- 不支持因费用、延迟或超预算而静默降级到 High/Low。

## Context Budget

模型调用前必须执行 `context_budget.py`，默认限制：

```yaml
max_allowed_files: 5
max_task_bytes: 32768
max_total_allowed_file_bytes: 262144
max_single_file_bytes: 131072
max_log_excerpt_lines: 300
include_chat_history: false
include_full_sop: false
```

Context Budget 必须先于读取 Relay Secrets、启动 Forwarder 和调用模型。失败时：

```text
不调用模型
→ 不消耗Codex额度
→ HUMAN_REQUIRED: 缩小允许文件或拆分任务
```

不得通过降低推理强度、附加完整聊天历史或复制完整 SOP 绕过预算。`context-budget.json` 必须进入 Secret Audit、Manifest、Handoff 和 Publish 复核。

## 结构化输出交接

官方 Action 使用 Output Schema 约束最终消息，并通过 `final-message` output 交给 Caller Job。不得把绝对 `/tmp` 路径作为第三方 Action 的 `output-file` input。

Caller Job 必须：

1. 通过环境变量读取 `steps.codex.outputs.final-message`，不得拼接成 Shell；
2. 使用 Python 解析 JSON；
3. 将规范化结果写入工作区外的 `/tmp/codex-result.json`；
4. 只有 Context、结果解析、Scope、Targeted Gate 和 Secret Audit 全部通过后才允许 Publish。

## 权限分离

- Codex Job：`agent-runtime`、`contents: read`、`persist-credentials: false`；
- Composite Action：只接收 Key、Model 和 Prompt inputs，不拥有 GitHub 写权限；
- Publish Job：`contents: write`，不声明 Environment，不接收 Relay Secret；
- Product Gate、Auto Recovery、Branch GC 和 Post-Merge 不得引用 Relay Secret；
- Job 间只传扫描过的 Patch、Manifest、Context、结构化结果和 Gate 摘要；
- `.agent/current_task.yaml` 在产品分支提交前必须移除。

## Thin Worker 边界

- 一个明确目标；
- 显式允许路径和禁止路径；
- 每个 Task Generation 一次 Session；
- XHigh；
- 一个 Targeted Gate；
- 不做总规划、业务口径、Secret/Workflow 变更、长报告或无限修复；
- 越界修改立即 `SECURITY_BLOCKED`，不得盲目重试。

## Recovery Generation

最多创建一个新的 Codex Recovery Generation。它必须：

- 从最新安全基线或失败产品分支创建；
- 继承 `allowed_files`、`forbidden_patterns`、Context Budget、Gate 和风险等级；
- 记录 parent task/run 和 generation；
- 不扩大权限、范围或上下文；
- 再失败时进入人工或阻断状态。

## 低风险自动合并

- 中高风险任务禁止自动合并；
- `.github/**`、`docs/**`、`src/**`、Schema、Secrets、业务口径和不可逆变更禁止自动合并；
- 只有 `risk_class=low`、`auto_merge=true`、允许文件不超过 5 个且 Context/Scope/Secret/Targeted/Full Gate 全部通过时才可受控合并；
- 冲突、权限或分支保护不允许强推，必须 `HUMAN_REQUIRED`；
- 自动合并后必须 exact-main Post-Merge。

## 触发与供应链安全

不支持：

- Fork PR 自动执行 Secret Job；
- `pull_request_target` 执行不可信代码；
- Issue/评论或自由文本中的任意 Shell；
- 未验证 Artifact 直接执行；
- 自动扩大修改范围；
- 无限 Codex 循环。

所有生产 Action 固定完整 commit SHA；阶段间使用显式 `workflow_dispatch` 或 `repository_dispatch`，Payload 仅含非 Secret 标识和经过验证的任务引用。
