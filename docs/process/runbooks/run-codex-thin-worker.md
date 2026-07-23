# Runbook：运行 Codex Thin Worker 与自动继续

## 适用条件

问题已明确诊断；修改范围通常不超过 2–5 个文件；无业务口径、Workflow/Secret、Schema 和破坏性迁移；有 Targeted、Full 和 Post-Merge Gate。

## schema-v2 任务描述

从模板生成 `.agent/current_task.yaml`：

```yaml
schema_version: 2
allowed_files: 明确路径
forbidden_patterns: 包含 .github/**、docs/**、secrets/**、.env
gate_profile: Targeted Gate
full_gate_profile: Full Gate
post_merge_profile: exact-main Gate
reasoning_effort: xhigh
context_budget:
  max_allowed_files: 5
  max_task_bytes: 32768
  max_total_allowed_file_bytes: 262144
  max_single_file_bytes: 131072
  max_log_excerpt_lines: 300
  include_chat_history: false
  include_full_sop: false
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

1. Web Supervisor 先写 `Wxx_plan.md`；
2. 从最新 `main` 创建 `task/codex-<slug>` 并提交不含 Secret 的 Descriptor；
3. `workflow_dispatch` 启动默认分支上的 `Codex Task`；
4. 入口验证 actor、控制分支和 Task Descriptor；
5. Secret-bearing Job 直接声明 `agent-runtime`，权限为 `contents: read`；
6. **在读取 Relay Secret 和模型调用前**运行 Context Budget；
7. Context PASS 后注册 Mask、验证 Runtime、启动 localhost Forwarder；
8. Composite Action 以 `effort: xhigh` 执行一次 Session；
9. Output Schema 约束 `final-message`，Caller 用 Python 写入 `/tmp/codex-result.json`；
10. 同一只读 Job 执行 Scope、Targeted Gate、Secret Audit 和 Manifest；
11. Handoff 同时包含 `context-budget.json`，Publish 必须再次验证；
12. Secret-free Publish 应用 Patch、重跑 Scope/G1、移除任务描述并推送产品分支；
13. 显式发送 `devflow_product_gate`；
14. Product Gate 执行 Scope、Full Gate、必要 rebase 和低风险自动合并；
15. 显式发送 `devflow_post_merge`；
16. exact-main PASS 后收尾、通知完成，并派发 Branch GC dry-run。

## Context Budget 失败

```text
Context Budget FAIL
→ Secrets不读取
→ Forwarder不启动
→ Codex不调用
→ 不消耗模型额度
→ 要求缩小允许文件或拆分任务
```

禁止通过降级推理强度、附加完整聊天历史、复制完整 SOP 或扩大日志来绕过预算。

## XHigh 兼容规则

- 生产 Composite Action 固定 `effort: xhigh`；
- 新模板和 Recovery Generation 使用 schema-v2/XHigh；
- schema-v1 `low` Descriptor 只读兼容，`effective_reasoning_effort` 仍为 XHigh；
- schema-v2 Low 直接拒绝；
- 已完成历史候选不因元数据迁移无意义重跑模型；
- Upgrade Compatibility 每次验证该边界。

## Secret 与输出边界

- Secret-bearing reusable workflow 不受支持；Environment 直接绑定普通 Job；
- 可复用性由本地 Composite Action提供；
- 不向第三方 Action 传绝对 `/tmp` output-file；
- 模型输出不得拼接为 Shell；
- Context、结果、Patch、Scope、Gate、Secret Audit 和 Manifest 位于工作区外；
- Publish、Product Gate、Post-Merge 和 Branch GC 不接收 Relay Secret。

## 自动恢复

- Runner、checkout、依赖、网络、Artifact：最多三次只重跑失败 Job；
- Codex 执行/G1：同一 Generation 最多定向重跑一次；
- Full/Post-Merge：最多创建一个继承原范围和 Context 的 schema-v2 XHigh Recovery Generation；
- Context、Scope、Secret、安全、业务决策、权限或预算耗尽才通知；
- 可恢复过程保持静默。

## 默认预算

```yaml
reasoning_effort: xhigh
codex_sessions_per_generation: 1
automatic_second_session: 0
max_recovery_generations: 1
infrastructure_retries: 3
context_budget:
  max_allowed_files: 5
  max_task_bytes: 32768
  max_total_allowed_file_bytes: 262144
  max_single_file_bytes: 131072
  max_log_excerpt_lines: 300
```

## 人工边界

以下任务不得自动合并：

- `.github/**`、Secrets、Schema 或迁移；
- 业务语义、官方来源优先级和研究口径；
- 允许路径超过 5 个或超 Context Budget；
- 无确定性 Full/Post-Merge Gate；
- 需要登录、验证码、外部账号配置或不可逆操作。
