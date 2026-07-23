# HANDOFF：chatgpt-web-codex-devflow-v1

## 当前事实

- 状态：RUNNING
- 阶段：W05
- 分支：`main`
- PR：30（基础设施已合并；Auto Recovery 增量正在独立 PR 中）
- 最后成功步骤：`canonical_issue_runtime_preflight_and_incident_hotfixes_merged`
- 下一动作：`merge_auto_recovery_controller_then_run_real_unattended_codex_thin_slice`

## 当前阻塞

无。此前的 `[TASK][INTERRUPTED]` 已被确认主要来自“原始 Workflow 失败即通知”的过早升级。当前改造在通知前加入确定性分类、失败 Job 有限重试、受限 Codex Recovery Generation、Product Gate、低风险自动合并和 exact-main Post-Merge。

## 最小人工动作

无。只有 Environment Secret/权限、业务决策、安全阻断、合并边界或恢复预算耗尽才需要人工。

## 恢复读取顺序

1. `task_state.yaml`
2. 最新 GitHub Checks、Auto Recovery Summary 与安全 Artifact
3. 当前 `Wxx_plan.md` / `Wxx_result.md`
4. 本文件
5. `docs/process/README.md`

## 重试预算

`{'infrastructure': 3, 'codex_sessions': 1, 'codex_recovery_generations': 1, 'same_root_cause_limit': 2, 'replans': 2}`

## 通知语义

`/ack` 只确认已看到，不触发修复、重试、Codex 或继续。正常可恢复错误应在预算内自动处理并保持静默。
