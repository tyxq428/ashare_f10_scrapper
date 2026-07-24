# 监控与零模型自动恢复政策

## 可观测性

- 预计超过五分钟的 Job 必须流式输出，或每 15–30 秒输出心跳。
- 心跳至少包含 UTC 时间、当前阶段、静默秒数和可安全公开的进度计数。
- 每个长 Job 必须设置超时和 stale 阈值。
- 不得使用 `subprocess.run(..., stdout=PIPE)` 完整缓冲长命令；使用 `Popen` 流式读取。
- ChatGPT Web 的思考动画不是任务状态。唯一可信状态来自 canonical state、Workflow conclusion、Commit SHA、PR 和 `HANDOFF.md`。

## 错误分类

```text
INFRA_RETRYABLE       普通零模型Job的Runner、Checkout、Setup、依赖或Artifact临时错误
MECHANICAL            Ruff、格式、缓存、临时文件、Git身份或状态渲染问题
IMPLEMENTATION        代码逻辑、类型、单元测试或完整Gate失败
CONTEXT_BUDGET        XHigh任务文件数/字节数/日志上下文超过批准预算
CODEX_TERMINAL        BLOCKED、未验证SUCCESS、无结果、失败、超时或取消
PAID_PROBE_FAILURE    Relay付费探针的认证、协议、余额、限流、超时或传输失败
DATA_QUALITY          解析可疑、缺失、单位或期间异常
RESEARCH_REVIEW       来源冲突、覆盖缺口、部分来源不可用
PERMISSION_BLOCKED    登录、验证码、Environment Secrets、GitHub权限
BUSINESS_DECISION     业务口径、来源优先级、破坏性Schema
SECURITY_BLOCKED      Secret命中、修改越界、Manifest不一致
PARALLEL_CONFLICT     并行PR、自动合并冲突或共享状态冲突
UNCLASSIFIED          无法通过安全摘要确定恢复路径
```

## 自动恢复顺序

任何受管失败在通知用户前，先经过 `Devflow Auto Recovery`：

```text
失败Workflow
→ 下载Job/Step元数据和安全摘要Artifact
→ 生成root-cause fingerprint
→ 分类
   ├─ RETRY：只重跑白名单中的普通零模型基础设施Job
   ├─ NOOP：成功或无需动作
   └─ HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED：才通知
```

不存在 `RETRY_CODEX`、`CODEX_REPAIR`、Recovery Generation 或自动模型 Dispatch。

## 永不进入自动重试的执行

以下 Workflow 或 Job 无论失败发生在哪个步骤，都不得调用 `rerun-failed-jobs`：

- `Codex Task` 或任何一次性模型 Activation；
- `Devflow Relay Health` 的 `paid_responses_probe`；
- 已经预占一次性 Grant 的 Job；
- 任何日志含 `CODEX_MODEL_SESSION_STARTED` 的 Run；
- Secret、Scope、Manifest 或权限边界失败。

原因：GitHub Actions 重跑的是整个失败 Job。即使失败发生在 Artifact 上传，仍可能从头再次执行已经付费的模型请求。

## 历史 Workflow Re-run 隔离

当前默认分支 Policy 不能追溯修改历史 Run 使用的 Workflow 定义。历史 `Codex Task` Re-run 可能再次解析当时的 `task/codex-*` 分支。

永久规则：

- 所有历史 `task/codex-*` 分支必须移除 `.agent/current_task.yaml`；
- 分支必须包含禁用 Composite Action，且不得包含 `openai/codex-action`；
- 分支必须包含 `.devflow/legacy-codex-rerun-quarantine.json`；
- 新建该前缀分支时立即运行 `Devflow Legacy Codex Rerun Audit`；
- 有开放 PR 的分支不自动修改，必须 Fail Closed 并由 ChatGPT Web审查。

## Relay Health

`Devflow Relay Health` 默认使用 `configuration_only`，只验证 Secret形状，不发送 Responses 请求。真实付费探针必须：

- 由 `tyxq428` 手工触发；
- 选择 `paid_responses_probe`；
- 输入精确确认短语；
- 提供非空目的；
- 每次最多发送一个请求；
- 不在 Auto Recovery监听列表中；
- 失败后不得自动重跑。

## Secret Audit

Secret Audit 不自动监听普通 `Codex Task`。在绑定 `agent-runtime` 前，零 Secret Job必须验证 Source Run 是：

- `Codex One-Time Activation`；
- 来自 `main`；
- 人工 `workflow_dispatch`；
- 已完成；
- 日志包含与输入 Activation ID匹配的模型启动标记。

## 预算

```yaml
ordinary_zero_model_infrastructure_retries: 3
codex_sessions: 0
codex_recovery_generations: 0
paid_probe_automatic_retries: 0
historical_model_reruns: 0
```

## Failure Bundle

Failure Bundle 只保留：

- 稳定错误分类和 root-cause fingerprint；
- 失败 Job/Step 名称；
- Context、Codex、Scope、Secret 和 Gate 安全摘要；
- 失败测试和当前 Diff 摘要；
- 已完成 Gate、剩余预算和最小人工动作；
- `HANDOFF.md` 恢复入口。

完整日志只留在短期 Artifact，不进入 Issue、仓库 Markdown 或通知邮件。
