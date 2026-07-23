# 监控与恢复政策

## 可观测性

- 预计超过五分钟的 Job 必须流式输出，或每 15–30 秒输出心跳。
- 心跳至少包含 UTC 时间、当前阶段、静默秒数和可安全公开的进度计数。
- 每个长 Job 必须设置超时和 stale 阈值。
- 不得使用 `subprocess.run(..., stdout=PIPE)` 完整缓冲长命令；使用 `Popen` 流式读取。

## 错误分类

```text
INFRA_RETRYABLE       HTTP 408/425/429/5xx、超时、DNS、TLS、临时连接错误
MECHANICAL            Ruff、格式、可确定修复的缓存或依赖问题
IMPLEMENTATION        代码逻辑、类型、单元测试失败
DATA_QUALITY          解析可疑、缺失、单位或期间异常
RESEARCH_REVIEW       来源冲突、覆盖缺口、部分来源不可用
PERMISSION_BLOCKED    登录、验证码、Secrets、GitHub 权限
BUSINESS_DECISION     业务口径、来源优先级、破坏性 Schema
SECURITY_BLOCKED      Secret 命中、修改越界、Manifest 不一致
PARALLEL_CONFLICT     并行 PR 路径或共享状态冲突
```

## 恢复

- 网络错误只重试失败步骤、失败组或失败 Job，保留成功缓存。
- 默认最多三次基础设施重试、一次局部代码修复；Codex 不自动开启第二个 Session。
- 同一根因连续两次仍失败，生成 Failure Bundle 并进入 `INTERRUPTED` 或 `HUMAN_REQUIRED`。
- Failure Bundle 只保留首个根错误、相关调用栈、失败测试、当前 Diff 摘要、已完成 Gate 和恢复命令；完整日志留在 Artifact。
- 任何恢复都必须从最新稳定检查点继续，禁止无理由全量重跑。
