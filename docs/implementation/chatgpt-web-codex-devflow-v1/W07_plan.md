# W07 计划：后续低风险任务渐进迁移标准

## 目标

薄切片通过后，将后续低风险代码任务逐步迁移到自动执行流，而不是一次性强制所有任务使用 Codex。

## 默认适用条件

只有同时满足以下条件，任务才可以启用自动合并：

- 修改目标已由 ChatGPT Web 或任务合同明确；
- `risk_class=low`；
- 允许修改路径为 1–5 个明确文件；
- 有 Targeted、Full 和 Post-Merge Gate；
- 不修改 `.github/**`、Secrets、数据 Schema、官方来源优先级或研究口径；
- 不包含破坏性迁移；
- 单个任务代次只允许 1 个 Codex Session；
- Full/Post-Merge 失败最多创建 1 个 recovery generation；
- 自动恢复预算耗尽后才通知用户。

## 观察指标

后续三个低风险任务持续记录：

```yaml
scope_violations: 0
secret_audit_failures: 0
automatic_recovery_generations: <= 1 per task
targeted_gate_pass_rate: 100%
post_merge_pass_rate: 100%
rollback_count: 0
human_notifications_for_retryable_errors: 0
```

## 路由策略

### 自动执行流

适用于明确 Bug、局部重构、回归测试、字段映射和机械性代码修复。

### ChatGPT Web 直接处理

适用于业务口径、数据语义、来源冲突、架构设计、Workflow/Secret 基础设施和破坏性变更。

## 完成标准

- 策略写入 Policy、Runbook 和 task template；
- Task Descriptor 验证器能够拒绝高风险自动合并；
- Auto Recovery、Product Gate 和 Post-Merge 使用同一预算语义；
- 新任务不需要每次重新粘贴完整 SOP。
