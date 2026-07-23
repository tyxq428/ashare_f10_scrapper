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
3. 通过 `workflow_dispatch` 显式启动默认分支上的 `Codex Task`，输入只包含可信控制分支名；不依赖任务分支 Push。
4. `Codex Task` 验证 Task Descriptor，并在普通 Job 上直接声明 `environment: agent-runtime`。
5. 入口只允许仓库所有者或 `github-actions[bot]`；Composite action显式配置 `allow-bots: true` 和 `allow-bot-users: github-actions[bot]`，不开放任意用户或 Bot。
6. Secret-bearing Codex Job 以 `contents: read` checkout 控制分支，运行安全预检和 localhost Forwarder，再调用 `.github/actions/codex-thin-worker/action.yml` 完成一次 Codex Session。
7. 官方 Action 在 Output Schema约束下返回 `final-message`；Caller Job通过环境变量交给 Python解析，规范化写入工作区外的 `/tmp/codex-result.json`，不得把模型输出拼接为 Shell。
8. 同一 Secret-bearing Job继续执行 Scope Guard、Targeted Gate、Secret Audit 和 Patch Manifest；Composite action只接收显式 Key/Model inputs，不直接读取 `secrets.*`。
9. Secret-free Publish Job验证 Manifest、应用 Patch、重跑 Targeted Gate，移除任务描述后 Push 隔离产品分支。
10. Publish 成功后显式发送 `devflow_product_gate`，不依赖 Push 递归触发。
11. Product Gate从控制分支重新读取 immutable descriptor，执行 Scope Guard 和 Full Gate。
12. 若 `risk_class=low` 且 `auto_merge=true`，同步最新 `main`、必要时 rebase并重跑 Gate，然后自动合并。
13. 合并后显式发送 `devflow_post_merge`，在 exact main执行 Post-Merge Profile。
14. Post-Merge通过后自动更新 canonical state、阶段结果和最终报告；`notify_completion=true` 时发送一次完成通知。

## 为什么不用 Secret-bearing reusable workflow

`agent-runtime` Environment Secrets必须直接绑定到入口 Workflow的普通 Job。正式探针已证明普通 Job可以读取三项 Secret，而旧本地 `workflow_call` 边界中的同名表达式为空。后续可复用性由 composite action提供；不得重新把 Environment Secret Job移回 reusable workflow。

## 为什么不用绝对 output-file

官方 Action示例将 `output-file` 放在仓库相对路径，且始终提供 `final-message` output。为了避免工作区 Scope Guard污染和绝对路径兼容性差异，正式流程不向官方 Action传 `/tmp` output-file，而是从 `final-message` 安全写入 `/tmp`。

## 自动恢复

- Runner、checkout、依赖、网络、Artifact 等基础设施失败：最多三次只重跑失败 Job，静默。
- Codex Task失败：同一 Task Generation最多定向重跑一次失败 Job，静默。
- Full/Post-Merge Gate失败：在允许范围内最多创建一个 Recovery Generation，静默。
- Recovery Generation继承原范围和 Gate，不允许扩大文件清单。
- Scope/Secret安全失败、业务决策、权限或预算耗尽才通知。

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

- `.github/**` 或 Secrets变更；
- 业务语义、官方来源优先级和研究口径；
- 数据 Schema或破坏性迁移；
- 允许路径超过 5 个；
- 无确定性 Full/Post-Merge Gate；
- 需要登录、验证码、外部账号配置或不可逆操作。
