# W05 计划：PR-A 合并与独立 Post-Merge

## 目标

同步最新 main，重复并行开发审计，完成 PR-A pre-merge Gate；合并后在 exact main 独立执行状态、Workflow 安全、devflow tests 和现有完整 Test。

## 完成标准

- 临时 Workflow 已移除；
- PR-A 与 main 无未解决冲突；
- pre-merge State Consistency 与 Test 通过；
- 合并后 `Devflow Infrastructure Post Merge` 通过；
- 正式 `agent-runtime` Relay Health 通过；
- 通过后才能创建 W06 真实 Codex 控制分支。

## 人工门槛

仅限合并冲突、正式 Secrets/权限缺失、安全审计或 exact-main 回归失败。
