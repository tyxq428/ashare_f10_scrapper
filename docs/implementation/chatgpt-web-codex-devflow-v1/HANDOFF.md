# HANDOFF：chatgpt-web-codex-devflow-v1

## 当前事实

- 状态：RUNNING
- 阶段：W05
- 分支：`main`
- PR：30、34、35、37 已合并；W05-HF04 独立热修复正在验证
- 最后成功步骤：`auto_recovery_merged_and_direct_agent_runtime_presence_probe_passed`
- 下一动作：`merge_direct_environment_boundary_hotfix_then_run_fresh_unattended_codex_thin_slice`

## 当前阻塞

无人工阻塞。安全探针已证明正式 `agent-runtime` 普通 Job 可以读取 Endpoint、Key 和 Model；旧 Codex 失败来自本地 reusable workflow 的 Environment Secret 可见性边界。当前热修复把 Environment 直接绑定到入口普通 Job，并使用本地 composite action复用 Codex 调用。

## 最小人工动作

无。Secret 名称、值和部署分支规则已经由用户确认；后续由 GitHub Actions 继续。只有 Environment/权限再次真实失败、业务决策、安全阻断、合并边界或恢复预算耗尽才通知。

## 恢复读取顺序

1. `task_state.yaml`
2. 最新 GitHub Checks、Auto Recovery Summary 与安全 Artifact
3. `W05_HF04_plan.md` 与最新结果
4. 本文件
5. `docs/process/README.md`

## 重试预算

`{'infrastructure': 3, 'codex_sessions': 1, 'codex_recovery_generations': 1, 'same_root_cause_limit': 2, 'replans': 2}`

## 通知语义

`/ack` 只确认已看到，不触发修复、重试、Codex 或继续。正常可恢复错误应在预算内自动处理并保持静默。
