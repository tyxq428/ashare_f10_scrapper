# 监控与自动恢复政策

## 可观测性

- 预计超过五分钟的 Job 必须流式输出，或每 15–30 秒输出心跳。
- 心跳至少包含 UTC 时间、当前阶段、静默秒数和可安全公开的进度计数。
- 每个长 Job 必须设置超时和 stale 阈值。
- 不得使用 `subprocess.run(..., stdout=PIPE)` 完整缓冲长命令；使用 `Popen` 流式读取。
- ChatGPT Web 的思考动画不是任务状态。唯一可信状态来自 canonical state、Workflow conclusion、Commit SHA、PR 和 `HANDOFF.md`。

## 错误分类

```text
INFRA_RETRYABLE       HTTP 408/425/429/5xx、超时、DNS、TLS、临时连接、Runner/Artifact错误
MECHANICAL            Ruff、格式、可确定修复的缓存、临时文件或状态渲染问题
IMPLEMENTATION        代码逻辑、类型、单元测试或完整Gate失败
DATA_QUALITY          解析可疑、缺失、单位或期间异常
RESEARCH_REVIEW       来源冲突、覆盖缺口、部分来源不可用
PERMISSION_BLOCKED    登录、验证码、Environment Secrets、GitHub权限
BUSINESS_DECISION     业务口径、来源优先级、破坏性Schema
SECURITY_BLOCKED      Secret命中、修改越界、Manifest不一致
PARALLEL_CONFLICT     并行PR、自动合并冲突或共享状态冲突
UNCLASSIFIED          无法通过安全摘要确定恢复路径
```

## 自动恢复顺序

任何失败在通知用户前，必须先经过 `Devflow Auto Recovery`：

```text
失败Workflow
→ 下载Job/Step元数据和安全摘要Artifact
→ 生成root-cause fingerprint
→ 分类
   ├─ RETRY：只重跑失败Job
   ├─ RETRY_CODEX：同一Task Generation定向重跑一次失败Codex Job
   ├─ CODEX_REPAIR：创建一个受限Recovery Generation
   ├─ NOOP：成功或无需动作
   └─ HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED：才通知
```

## 预算

```yaml
infrastructure_retries: 3
codex_sessions_per_generation: 1
automatic_second_session: 0
codex_recovery_generations: 1
same_root_cause_limit: 2
```

- 基础设施错误只重试失败步骤、失败组或失败 Job，保留成功缓存。
- Codex 单个 Task Generation 只运行一次 Session；失败 Job 可以按策略重跑一次，但不会在同一 Session 内无限循环。
- Targeted、Full 或 Post-Merge Gate 失败且仍在批准范围内时，最多创建一个新的受限 Codex Recovery Generation。
- Recovery Generation 必须继承原允许路径、禁止路径、风险等级和 Gate，不得自动扩大范围。
- 预算内恢复保持静默，不创建 Issue 评论、不发邮件。
- 同一根因超过预算、无法安全分类或出现真正人工门槛后，才生成 Failure Bundle 并进入 `INTERRUPTED`、`HUMAN_REQUIRED` 或 `SECURITY_BLOCKED`。
- 任何恢复都必须从最新稳定检查点继续，禁止无理由全量重跑。

## Failure Bundle

Failure Bundle 只保留：

- 稳定错误分类和 root-cause fingerprint；
- 失败 Job/Step 名称；
- 首个相关错误摘要；
- 失败测试和当前 Diff 摘要；
- 已完成 Gate、剩余预算和最小人工动作；
- `HANDOFF.md` 恢复入口。

完整日志只留在短期 Artifact，不进入 Issue、仓库 Markdown 或通知邮件。
