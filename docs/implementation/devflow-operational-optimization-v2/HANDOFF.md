# HANDOFF：devflow-operational-optimization-v2

## 当前事实

- 状态：VERIFYING
- 执行状态：RUNNING
- 领域验收：generic/PENDING
- 安全状态：PENDING
- 阶段：W01
- 分支：`feature/devflow-operational-optimization-v2`
- PR：44
- 最后成功步骤：`pull_request_44_opened`
- 下一动作：`monitor_pr44_fix_gates_then_force_full_test_and_real_e2e`

## 当前阻塞

无。PR #44 已创建；当前等待影响感知 Test/E2E、State Consistency、Upgrade Compatibility 和静态安全门禁提供事实。

## 最小人工动作

无。除真实权限、安全、不可逆风险或业务决策外连续执行。

## 恢复读取顺序

1. `task_state.yaml`
2. PR #44 最新 GitHub Checks、分支 HEAD 与 main HEAD
3. 当前 `Wxx_plan.md` / `Wxx_result.md`
4. 本文件
5. `docs/process/README.md`

## 本任务特殊要求

- 所有未来真实 Codex 调用由生产 Composite Action 强制 XHigh；
- Context Budget 在读取 Relay Secret 和模型调用前 Fail Closed；
- 本任务属于 Workflow/Devflow 基础设施改造，不调用 Codex；
- 生产 Auto Recovery 不执行相同 Generation 的 `RETRY_CODEX`；
- Codex BLOCKED/未验证/无结果由 Circuit Breaker 停止，State Consistency 无 Descriptor 时禁止合成 scope；
- 影响感知 Gate 只缓存依赖，不缓存 Scope、Secret、Gate、Diff 或 Post-Merge 结论；
- Branch GC 第一阶段固定 dry-run；
- PR Gate 通过后还需一次强制完整 Test 和真实 E2E，证明人工 override 路径未被影响分类器屏蔽；
- main 上的一次性 emergency circuit-breaker patch Workflow 在合并后单独清理。

## 重试预算

`{'infrastructure': 3, 'codex_sessions': 1, 'codex_recovery_generations': 1, 'same_root_cause_limit': 2, 'replans': 2}`
