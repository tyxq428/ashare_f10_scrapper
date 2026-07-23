# Runbook：运行 Codex Thin Worker 与自动继续

## 适用条件

问题已被明确诊断；修改范围通常不超过 2–5 个文件；无业务口径、Workflow/Secret、Schema 和破坏性迁移；有 Targeted、Full 和 Post-Merge Gate。

## 任务描述

从模板生成 `.agent/current_task.yaml`，必须包含：

```yaml
allowed_files: 明确路径
forbidden_patterns: 包含 .github/**、docs/**、secrets/**、.env
gate_profile: Targeted Gate
full_gate_profile: Full Gate
post_merge_profile: exact-main Gate
risk_class: low | medium | high
auto_merge: true | false
notify_completion: true | false
expected_base_sha: 当前main SHA
session_limit: 1
automatic_second_session: 0
recovery_generation: 0
max_recovery_generations: 1
```

## 正常成功路径

1. Web Supervisor 先写当前 `Wxx_plan.md`。
2. 从最新 `main` 创建 `task/codex-<slug>` 控制分支并提交任务描述；任务中不得包含 Secret。
3. `Codex Task` 验证 Task Descriptor，再调用 reusable workflow。
4. Secret-bearing Codex Job 以 `contents: read` 运行 localhost Forwarder、一次 Codex Session、Scope Guard、Targeted Gate、Secret Audit 和 Patch Manifest。
5. Secret-free Publish Job 验证 Manifest、应用 Patch、重跑 Targeted Gate，移除任务描述后 Push 隔离产品分支。
6. Publish 成功后显式发送 `devflow_product_gate`，不依赖 Push 递归触发。
7. Product Gate 从控制分支重新读取 immutable descriptor，执行 Scope Guard 和 Full Gate。
8. 若 `risk_class=low` 且 `auto_merge=true`，同步最新 `main`、必要时 rebase 并重跑 Gate，然后自动合并。
9. 合并后显式发送 `devflow_post_merge`，在 exact main 执行 Post-Merge Profile。
10. Post-Merge 通过后自动更新 canonical state、阶段结果和最终报告；`notify_completion=true` 时发送一次完成通知。

## 自动恢复

- Runner、checkout、依赖、网络、Artifact 等基础设施失败：最多三次只重跑失败 Job，静默。
- Codex Task 失败：同一 Task Generation 最多定向重跑一次失败 Job，静默。
- Full/Post-Merge Gate 失败：在允许范围内最多创建一个 Recovery Generation，静默。
- Recovery Generation 继承原范围和 Gate，不允许扩大文件清单。
- Scope/Secret 安全失败、业务决策、权限或预算耗尽才通知。

## 默认预算

```yaml
reasoning_effort: low
codex_sessions_per_generation: 1
automatic_second_session: 0
max_recovery_generations: 1
infrastructure_retries: 3
output_tokens_observation_limit: 2000
total_input_tokens_observation_limit: 100000
```

## 人工边界

以下任务不得开启自动合并：

- `.github/**` 或 Secrets 变更；
- 业务语义、官方来源优先级和研究口径；
- 数据 Schema 或破坏性迁移；
- 允许路径超过 5 个；
- 无确定性 Full/Post-Merge Gate；
- 需要登录、验证码、外部账号配置或不可逆操作。
