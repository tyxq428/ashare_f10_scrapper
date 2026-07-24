# 监控与零模型自动恢复政策

## 可观测性

- 预计超过五分钟的 Job 必须流式输出，或每 15–30 秒输出心跳；
- 心跳至少包含 UTC 时间、当前阶段、静默秒数和可安全公开的进度计数；
- 每个长 Job 必须设置超时和 stale 阈值；
- 不得完整缓冲长命令输出；使用 `Popen` 或等价流式方式；
- ChatGPT Web 的思考动画不是任务状态。唯一可信状态来自 canonical state、Workflow conclusion、Commit SHA、PR 和 `HANDOFF.md`。

## 错误分类

```text
INFRA_RETRYABLE       Runner、Checkout、Setup、依赖和Artifact的明确临时失败
MECHANICAL            Ruff、格式、Import、Fixture、缓存、Git身份或状态渲染
IMPLEMENTATION        代码逻辑、类型、单元测试或完整Gate失败
CONTEXT_BUDGET        任务文件数、字节数或日志上下文超过预算
CODEX_TERMINAL        BLOCKED / NO_CHANGES / UNVERIFIED / FAILURE / TIMEOUT
DATA_QUALITY          解析可疑、缺失、单位或期间异常
RESEARCH_REVIEW       来源冲突、覆盖缺口、部分来源不可用
PERMISSION_BLOCKED    登录、验证码、Environment、GitHub权限
BUSINESS_DECISION     业务口径、来源优先级、破坏性Schema
SECURITY_BLOCKED      Secret命中、修改越界、Manifest不一致
PARALLEL_CONFLICT     并行PR、合并冲突或共享状态冲突
UNCLASSIFIED          无法通过安全摘要确定恢复路径
```

## 自动恢复顺序

```text
失败Workflow
→ 下载Job/Step元数据和安全摘要Artifact
→ 生成root-cause fingerprint
→ 分类
   ├─ RETRY：只重跑受信任、模型前的基础设施失败Job
   ├─ NOOP：成功或无需动作
   └─ CHATGPT_WEB / HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED
```

不存在 `RETRY_CODEX`、`CODEX_REPAIR` 或 Recovery Generation。Product Gate、Post-Merge、State Consistency 和 Codex Task 均不能被 Auto Recovery 派发或重跑模型。

## 模型 Job 熔断

未来一次性 Activation 中：

- 模型前的 Prepare Job 可以有限重试；
- Grant 在模型 Job 前进入 `RESERVED`；
- Model-bearing Job 一旦预占 Grant即不可自动重跑；
- Checkout、Setup、模型请求、Artifact 上传、取消或超时任一失败都消耗当前 Grant；
- `BLOCKED / NO_CHANGES / UNVERIFIED / FAILURE / TIMEOUT` 都是当前 Grant 的终态；
- GitHub UI Re-run、重复 Dispatch 或不同分支同 Fingerprint 均在模型前被账本阻断；
- 后续只允许 ChatGPT Web 根据新事实决定是否创建新的任务和新的用户授权。

## 预算

```yaml
infrastructure_retries_before_model: 3
codex_sessions_per_grant: 1
automatic_second_session: 0
codex_recovery_generations: 0
calls_per_task: 1
calls_per_failure_fingerprint: 1
grant_ttl_minutes_max: 60
```

- 基础设施错误只重试失败 Job，保留成功检查点；
- State、Workflow、Devflow、Full Gate 和 Post-Merge 失败交给 ChatGPT Web；
- Scope、Secret 和 Manifest 失败进入 Security Block；
- Merge conflict、Branch Protection 和权限拒绝进入 Human Required；
- 同一根因无法安全自动恢复时生成 Failure Bundle；
- 禁止无理由全量重跑。

## Failure Bundle

只保留：

- 稳定错误分类和 root-cause fingerprint；
- 失败 Job/Step 名称；
- Context、Scope、Secret、Gate 和 Grant 的安全摘要；
- 失败测试和当前 Diff 摘要；
- 已完成 Gate、剩余基础设施预算和最小人工动作；
- `HANDOFF.md` 恢复入口。

完整日志只留在短期 Artifact，不进入 Issue、仓库 Markdown 或通知邮件。
