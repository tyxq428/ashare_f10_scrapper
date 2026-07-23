# 安全、Codex Thin Worker 与最小使用政策

## 总原则

Codex **默认禁用**。ChatGPT Web Supervisor 和确定性 GitHub Actions 是正常执行路径。仓库级总开关位于：

```text
.devflow/codex-policy.yaml
```

只要 `mode: disabled`：

- `codex-task.yml` 不得包含模型 Job；
- 不得声明 `agent-runtime`；
- 不得读取 Relay Secret；
- 不得启动 localhost Forwarder；
- 不得引用 `openai/codex-action`；
- 只能输出 `CODEX_MODEL_INVOCATION=DISABLED`。

本仓库在本轮优化完成后仍保持禁用。重新启用必须同时具备用户明确要求和独立受审 PR。

## Secret 边界

中转站 URL、hostname、API Key 和模型 ID 全部视为 Secret，只能存入 GitHub Environment `agent-runtime`：

```text
AGENT_RESPONSES_ENDPOINT
AGENT_API_KEY
AGENT_MODEL
```

它们不得进入仓库、Variables、日志、Issue、PR、Artifact、Failure Bundle 或异常正文。任何未来模型 Job 必须：

- `contents: read`；
- `persist-credentials: false`；
- 与 Publish Job 权限分离；
- 通过 localhost-only、无日志 Forwarder；
- 扫描完整值、hostname、URL 编码、Base64 和 Base64URL 变体。

当前禁用状态下，Codex Task 在该边界之前终止，因此不会接触这些 Secret。

## 默认执行路由

下列任务禁止使用 Codex，必须由 ChatGPT Web、确定性脚本或人工处理：

- `.github/**`、Devflow Core、状态模型和恢复分类；
- `AGENTS.md`、Policies、Runbooks、Templates 和任务状态文档；
- Ruff、格式、Import、Fixture、路径和 Schema 兼容问题；
- Secret、权限、安全、Branch Protection 和 Merge Boundary；
- 业务口径、数据源优先级、研究语义和架构决策；
- State Consistency、Product Gate 和 Post-Merge 失败；
- 已经返回 `BLOCKED / NO_CHANGES / UNVERIFIED / FAILURE / TIMEOUT` 的任务；
- 失败无法在模型调用前稳定复现的任务。

## 将来候选的必要条件

只有同时满足以下条件，任务才可被标记为 Codex 候选；候选并不自动执行：

1. 用户针对该任务明确授权；
2. Task Descriptor 不可变，并绑定 SHA-256；
3. 失败在零 Token 的 `pre_model_gate` 中可复现；
4. 失败指纹与授权完全一致；
5. 失败文件全部包含在 2–5 个 `allowed_files` 中；
6. 允许范围不包含 Workflow、Devflow、文档、Secret、Schema、迁移或业务语义；
7. Context Budget 通过；
8. Usage Ledger 中该任务和指纹均未使用；
9. `session_limit=1`、`automatic_second_session=0`、`recovery_generations=0`；
10. 独立受审 PR 恢复模型 Job，且用户再次明确要求执行。

任一条件失败时路由为 `CHATGPT_WEB`，不得“先让 Codex 试试”。

## Context Budget

若将来启用 XHigh，会话必须使用固定预算：

```yaml
max_allowed_files: 5
max_task_bytes: 32768
max_total_allowed_file_bytes: 262144
max_single_file_bytes: 131072
max_log_excerpt_lines: 300
include_chat_history: false
include_full_sop: false
```

不得通过降低推理强度来解决成本问题；应缩小任务、文件和失败证据。Schema v1 的 `low` 只作为历史只读元数据，运行时不得降级。

## 自动化禁止项

永久禁止：

- `github-actions[bot]` 派发 Codex；
- Auto Recovery 创建或 Dispatch Codex Recovery Generation；
- `rerun-failed-jobs` 重跑 Codex Session；
- State Consistency 根据固定文件列表合成任务；
- Post-Merge 自动调用模型修复；
- Issue 评论、Fork PR 或自由文本直接触发 Secret Job；
- `pull_request_target` 执行不可信代码；
- 自动扩大 `allowed_files`；
- 无限模型循环。

## 结构化终态

以下模型结果全部是当前 Generation 的终态：

```text
BLOCKED
NO_CHANGES
UNVERIFIED
FAILURE
TIMEOUT
```

出现后不得重跑相同 Job、相同指纹或相同 Descriptor。ChatGPT Web 读取不可变证据后，可以直接修复，或在用户重新授权后创建全新的任务。

## Patch 与 Gate 隔离

若未来恢复模型调用：

1. 模型结束后立即只对 `allowed_files` 生成 Patch；
2. 保存 Patch Hash；
3. Gate 输出全部写到 `/tmp`；
4. Gate 后再次确认 Patch Hash 未变化；
5. 结构化 `changed_files`、实际 Patch 文件和允许范围必须一致；
6. Scope、Secret、Manifest 或 Gate 任一失败均不得 Publish。

## 低风险合并

当前禁用状态下不会产生新的 Codex Candidate。未来即使重新启用，也只有显式批准的低风险任务、最多 5 个安全文件、全部 Gate 通过且 exact-main Post-Merge 通过时才可受控合并。冲突、权限或分支保护必须 `HUMAN_REQUIRED`，不得强推。
