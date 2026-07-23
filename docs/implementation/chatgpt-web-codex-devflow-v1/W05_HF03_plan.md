# W05-HF03 计划：自动恢复控制器与无人值守低风险执行链

## 背景

当前执行流已经具备 Codex Thin Worker、确定性 Gate、Canonical State 和任务控制 Issue，但失败通知仍直接监听任意 Workflow 的非成功终态。结果是：

- 一次可重试基础设施故障就立即产生 `[TASK][INTERRUPTED]`；
- 自动修复尚未尝试，用户却已经被要求回到 ChatGPT Web；
- `/ack` 仅确认收到，并不会触发修复；
- Codex 成功发布分支后，后续完整 Gate、合并与 Post-Merge 仍依赖 Web 会话；
- 聊天页面停止输出时，用户难以仅凭仓库状态判断任务是否仍在推进。

## 目标状态

```text
任务开始
→ GitHub Actions 执行
→ 可恢复错误自动分类并有限重试
→ 明确局部代码失败由一次受限 Codex 修复
→ 自动进入完整 Gate
→ 显式低风险任务自动合并
→ 自动执行独立 Post-Merge
→ 仅在真正人工门槛、Security Blocked、预算耗尽或最终完成时通知
```

## 工作范围

### 1. 自动恢复控制器

新增 `Devflow Auto Recovery`：

- 监听受管 Workflow 的终态；
- 读取 Job/Step 元数据与安全摘要 Artifact；
- 生成确定性分类：`NOOP / RETRY / CODEX_REPAIR / HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED / COMPLETED`；
- 基础设施类错误在预算内仅重跑失败 Job；
- 同一 Codex 任务只允许一次自动恢复代次；
- 预算内恢复保持静默，不写任务控制 Issue。

### 2. 高价值通知前置门禁

重构 `Devflow Incident`：

- 不再直接监听所有 `workflow_run` 失败；
- 只消费 Auto Recovery 或 Post-Merge 显式发送的 `repository_dispatch`；
- `/ack` 文案明确为“仅确认收到，不触发修复”；
- 只有 `COMPLETED / HUMAN_REQUIRED / SECURITY_BLOCKED / INTERRUPTED` 通知；
- 使用 canonical Issue #32 与 root-cause fingerprint 去重。

### 3. Codex 后自动继续

Codex Publish 成功后：

- 显式发送 `devflow_product_gate`；
- Product Gate 从控制分支读取受信任任务描述；
- 重跑 changed-path scope、目标 Gate 和完整仓库 Gate；
- Gate 失败时，在允许的单次恢复预算内创建新的受限 Codex 修复任务；
- 不使用任意用户 Shell 输入。

### 4. 显式低风险自动合并

只有任务描述同时满足以下条件时自动合并：

```yaml
risk_class: low
auto_merge: true
expected_base_sha: <40-char main SHA>
allowed_files: 1-5 个明确路径
forbidden_patterns: 包含 .github/**、secrets/**、.env
```

自动合并前必须：

- 当前 `main` 与 `expected_base_sha` 一致，或完成无冲突重放并重新 Gate；
- Scope Guard、Secret Audit、Targeted Gate、Full Gate 全部 PASS；
- 不修改 Workflow、Secret、业务 Schema、数据源优先级或研究口径；
- 使用受控 merge commit，随后通过 `repository_dispatch` 启动独立 Post-Merge。

### 5. 独立 Post-Merge 与最终通知

- Post-Merge 在 exact `main` 上重新执行目标 Gate 和完整回归；
- 失败时先按相同预算自动恢复；
- 成功时更新 canonical state、生成结果文档和 Final Report；
- 仅发送一次 `[TASK][COMPLETED]` 并关闭控制 Issue。

## 失败分类和预算

```yaml
auto_recovery:
  infrastructure_retries: 3
  codex_initial_sessions: 1
  codex_repair_generations: 1
  deterministic_repairs: 2
  same_root_cause_limit: 2
```

### 自动处理且静默

- `cancelled / timed_out / stale / startup_failure`；
- checkout、setup、依赖安装、Artifact 上传下载等临时失败；
- Relay/模型临时传输失败；
- 已知机械错误与确定性状态渲染错误；
- Product Gate 的一次明确局部代码修复。

### 必须通知

- Environment Secret 缺失、权限或验证码；
- 业务语义、来源优先级或破坏性迁移决策；
- Secret Audit 或敏感范围检查失败；
- 同一根因超过预算；
- Codex 修改越界；
- 自动合并遇到冲突或分支保护阻止且无法安全继续。

## 安全边界

- Relay URL、hostname、Key 和模型 ID 仍只存在于 Environment Secrets；
- Auto Recovery 不读取或打印 Secret 值；
- Secret-bearing Codex Job 保持 `contents: read`；
- Publish/Product Gate/Auto Recovery Job 不引用 Relay Environment；
- 通过 `repository_dispatch` 显式接力，避免依赖 `GITHUB_TOKEN` Push 自动触发；
- Action 固定完整 SHA；
- 原始 HTTP 日志、完整环境和 `$HOME` 不上传 Artifact；
- 自动合并仅适用于任务描述中明确批准的低风险范围。

## 计划修改

- `.github/workflows/devflow-auto-recovery.yml`
- `.github/workflows/devflow-product-gate.yml`
- `.github/workflows/devflow-incident.yml`
- `.github/workflows/devflow-post-merge.yml`
- `.github/workflows/_reusable-codex-thin-worker.yml`
- `.github/workflows/codex-task.yml`
- `scripts/devflow/recovery_policy.py`
- `scripts/devflow/recovery_task.py`
- `scripts/devflow/task_descriptor.py`
- `scripts/devflow/gate_profiles.py`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- 相关 Policies、Runbooks、Templates 与工程经验库

## 验收 Gate

```text
python -m compileall -q scripts/devflow
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
现有完整 Test
现有 E2E 688521
```

合并后再执行：

1. 一个不调用 Codex 的基础设施自动重试 Smoke Test；
2. 一个模拟 `HUMAN_REQUIRED` 的通知去重测试；
3. 当前 `resilient-command-terminal-status-v1` 真实低风险 Codex 薄切片；
4. 自动 Product Gate、自动合并和 exact-main Post-Merge；
5. 最终只产生一次完成通知。

## 恢复入口

```yaml
stage: W05_HF03
status: RUNNING
next_action: implement_auto_recovery_controller_and_automatic_continuation
human_intervention_required: false
```
