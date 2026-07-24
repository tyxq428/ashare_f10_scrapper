# 安全、Codex Thin Worker 与最小使用政策

## 总原则

Codex 默认禁用。ChatGPT Web Supervisor 和确定性 GitHub Actions 是正常执行路径。仓库级总开关：

```text
.devflow/codex-policy.yaml
```

`mode: disabled` 时，常驻入口不得包含模型 Job、`agent-runtime`、Relay Secret、Forwarder 或 `openai/codex-action`。重新启用不能只改 Policy；必须由用户针对具体任务明确要求，并通过独立受审的一次性 Activation PR。

## 唯一允许的潜在入口

机器清单位于：

```text
.devflow/codex-entrypoints.yaml
```

唯一允许项为 `manual_one_time_executor`。常驻 `codex-task.yml` 仅做零 Token 候选复核，不调用模型。

永久禁止：

- Product Gate、Post-Merge、State Consistency 或 Auto Recovery Dispatch Codex；
- `github-actions[bot]` 调用模型；
- `rerun-failed-jobs`、GitHub UI Re-run 或重复 Dispatch 重复模型会话；
- Recovery Generation；
- Issue 评论、Fork PR 或自由文本触发 Secret Job；
- 自动扩大 Allowed Files；
- 同一 Task、Fingerprint、Descriptor 或 Grant 第二次调用。

## 可信控制平面

未来所有资格和模型执行必须使用双 Checkout：

```text
control/
  exact main SHA
  Policy、Eligibility、Gate、Scope、Secret Audit、Grant逻辑

workspace/
  exact task SHA
  Descriptor与允许的产品代码
```

任务分支只能作为 data-only 工作区。任务分支中的 `.github/**`、`.devflow/**`、`scripts/devflow/**` 不得成为执行控制代码。

## 正向候选 Allowlist

仅以下 Reason Code 可进入候选：

```text
LOCAL_IMPLEMENTATION_DEFECT
LOCAL_TEST_GAP
BOUNDED_PURE_REFACTOR
```

并必须有 ChatGPT Web 必要性评估：

```yaml
attempted: true
can_complete_in_web: false
reason_code: LOCAL_ITERATIVE_TOOL_LOOP | BACKGROUND_WORKER_EXPLICITLY_REQUESTED
summary: 非空说明
```

未知原因、单文件简单修改、超过 5 个文件、机械问题、Workflow/Devflow、Full Gate、Post-Merge、Secret、安全、权限、业务语义和无法复现的失败全部路由 ChatGPT Web。

## 受信任 Pre-model 复现

任务分支自报 JSON 不能作为最终证据。Prepare Job 必须从精确控制 SHA 运行受信 Gate，绑定：

- Source Run ID 和 Source Commit SHA；
- 实际 Artifact SHA-256；
- Task Commit SHA；
- Gate Profile；
- 失败 Fingerprint；
- 真实 Failure Files。

Gate 已 PASS、证据不匹配或失败文件不被 Allowed Files 覆盖时，模型不得启动。

## Context Budget

```yaml
max_allowed_files: 5
max_task_bytes: 32768
max_total_allowed_file_bytes: 262144
max_single_file_bytes: 131072
max_log_excerpt_lines: 300
include_chat_history: false
include_full_sop: false
```

不得以降低推理强度绕过预算。若未来执行模型，只允许一次 XHigh Session。

## 一次性 Grant

Grant 必须：

- 由 `tyxq428` 通过 ChatGPT Web 明确批准；
- 绑定 Task SHA、Descriptor Digest、Source Run/SHA、Failure Fingerprint 与 Allowed Files Hash；
- `max_calls=1`；
- TTL 不超过 60 分钟；
- 初始状态为 `ISSUED`。

模型 Job 前，在按 Grant ID 序列化的 Workflow 中将 Ledger 写为 `RESERVED`；进入 `RESERVED` 后即视为调用名额已消耗。模型结束、失败、取消或超时后写为 `CONSUMED`。任何 Re-run 均返回 `GRANT_ALREADY_CONSUMED`。

## Secret 边界

Relay URL、hostname、API Key 和模型 ID 只能存在于 GitHub Environment `agent-runtime`，不得进入仓库、日志、Issue、PR 或 Artifact。一次性模型 Job必须：

- `contents: read`；
- `persist-credentials: false`；
- localhost-only 无日志 Forwarder；
- 与 Publish、Product Gate 和 Post-Merge 权限分离；
- 扫描完整值、hostname、URL 编码、Base64 和 Base64URL 变体。

## Patch 与 Gate 隔离

未来一次性 Activation 必须：

1. 模型结束后立即仅对 Allowed Files 生成 Patch；
2. 保存 Patch Hash；
3. Gate 输出全部写入 `/tmp`；
4. Gate 后确认 Patch Hash 未变化；
5. 结构化 Changed Files、实际 Patch 与 Allowed Files 一致；
6. Scope、Secret、Manifest 或 Gate 任一失败均不得 Publish。

## 终态

`BLOCKED / NO_CHANGES / UNVERIFIED / FAILURE / TIMEOUT` 都会消耗当前 Grant，并且不得重跑。后续只能由 ChatGPT Web直接处理，或在新的事实、新 Task SHA 和新的用户授权下创建全新一次性 Activation。
