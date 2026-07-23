# Runbook：运行 Codex Thin Worker

## 适用条件

问题已由 ChatGPT Web 诊断；修改范围通常不超过 2–5 个文件；无业务口径和破坏性迁移；有明确 G1。

## 步骤

1. Web Supervisor 写当前 `Wxx_plan.md`。
2. 从模板生成 `.agent/current_task.yaml`，填写目标、允许路径、禁止事项、`gate_profile`、发布分支和输出 Schema。
3. 从 `main` 或批准的产品分支创建 `task/codex-<slug>` 控制分支并提交任务文件；不要把 Secret 写入任务。
4. `Codex Task` 读取任务并调用 reusable workflow。
5. Codex Job 以只读仓库权限运行 localhost Forwarder、一次 Codex Session、Scope Guard、G1、Secret Audit 和 Patch Manifest。
6. Publish Job 在无 Relay Secret 的环境中重新校验、应用 Patch、重跑 G1、Commit 并 Push 隔离分支。
7. Web Supervisor 读取 Branch、Commit、Diff、Gate、Manifest 和审计结果，创建或更新 PR。
8. G2/G3/G4 在 Codex 会话外执行。失败后不自动再次调用 Codex；返回 Web 重新诊断。

## 默认预算

```yaml
reasoning_effort: low
codex_sessions: 1
automatic_second_session: 0
output_tokens_observation_limit: 2000
total_input_tokens_observation_limit: 100000
```
