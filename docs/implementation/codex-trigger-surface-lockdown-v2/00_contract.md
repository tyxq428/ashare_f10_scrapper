# 任务合同：Codex Trigger Surface Lockdown v2

## 目标

在 Codex 保持禁用、模型调用数保持 0 的前提下，继续审计并消除所有可能绕过当前 `main` 源码策略而触发 Codex Thin Worker 的残余路径，重点覆盖历史 Workflow Run 重跑、旧分支 Workflow、常驻手工入口和 `agent-runtime` Environment 边界。

## 硬约束

```yaml
codex_policy: disabled
codex_calls_during_task: 0
relay_model_request: forbidden
bot_codex_dispatch: forbidden
automatic_codex_retry: forbidden
automatic_recovery_generation: forbidden
historical_run_rerun_to_model: forbidden
```

## 完成定义

1. 当前 `main` 中不存在常驻模型执行 Workflow 或 Action；
2. `Codex Task` 常驻 Workflow 被删除或仓库级禁用，未来只能由一次性受审 Activation PR 恢复；
3. 历史 Codex Workflow Run 无法在未经过新审批边界的情况下重放到模型；
4. 已合并、无开放 PR 的旧受管分支中危险 Workflow 被删除、归档或安全对齐；
5. `agent-runtime` 的未来模型使用需要人工 Environment 审批；若平台 API 无法自动配置，必须 Fail Closed 并生成唯一最小人工配置动作；
6. 静态扫描、回归测试、完整 Test、真实 688521 E2E 和 exact-main 验证全部通过；
7. Canonical State、Wxx 结果和最终报告完成。
