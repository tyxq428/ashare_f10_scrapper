# 总体计划：Devflow Operational Optimization v2

## 总体执行流

```text
W00 基线与计划固化
→ W01 XHigh 指令一致性与 Context Budget
→ W02 影响感知 Gate 与依赖缓存
→ W03 平台状态/领域验收解耦
→ W04 已完成任务分支垃圾回收
→ W05 升级兼容与回归矩阵
→ W06 合并后验证、结果文档与收尾
```

除真实人工门槛外连续执行，不逐阶段请求“继续”。本任务属于 Workflow/Devflow 基础设施变更，不交给 Codex 自动修改，也不自动合并；由 ChatGPT Web Supervisor 创建 PR、读取 Checks、审查并在全部门禁通过后合并。

## W00｜基线与计划固化

### 目标

- 固定 `main` 基线与无开放 PR 事实；
- 建立合同、总体计划、Canonical State、Decision Log 与工作包计划；
- 审计当前硬编码和已知漂移：根 `AGENTS.md` 仍写 Low，而生产 Composite Action 已固定 XHigh；
- 建立改动路径和回滚边界。

### Gate

- 文档完整；
- 新任务在 `ACTIVE_TASKS.yaml` 唯一登记；
- 无并行 PR 路径冲突。

## W01｜XHigh 指令一致性与 Context Budget

### 目标

- 将根 `AGENTS.md`、Scoped Agent Rules、Policies、Runbooks 和模板统一为 XHigh；
- 生产 Composite Action 继续强制 `effort: xhigh`；
- 新 Descriptor 默认 XHigh，历史 schema-v1 Low Descriptor 仅用于读取兼容，不能降低运行时强度；
- 增加模型调用前 Context Budget，限制：
  - 允许文件数量；
  - Task Descriptor 字节数；
  - 允许文件累计字节数；
  - 单文件字节数；
  - 禁止携带聊天历史和完整 SOP；
  - 测试日志只允许有界摘要。

### 产物

- `scripts/devflow/context_budget.py`；
- Task Descriptor `context_budget` 字段；
- `codex-task.yml` 的模型调用前预算检查；
- 回归测试与 Policy/Runbook 更新。

### Gate

- 生产 Action 中不存在 `effort: low`；
- 新模板中不存在 `reasoning_effort: low`；
- 超预算任务在调用模型前 Fail Closed；
- 历史 Descriptor 兼容测试通过。

## W02｜影响感知 Gate 与依赖缓存

### 目标

将变更分为：

```text
docs_only
→ 文档链接/状态/Schema/Workflow静态检查

devflow_only
→ Devflow compile + Ruff + unit/contract smoke

product
→ 当前完整 Test + E2E + exact-main关键回归
```

### 实现

- 新增 `scripts/devflow/change_impact.py`，根据 Git diff 和受信路径规则输出影响等级与原因；
- `Test` Workflow 始终产生稳定 Check，但按影响等级运行最小充分步骤；
- `E2E 688521` 始终产生稳定 Check，只有 `product` 影响或手工强制时运行真实抓取；
- Devflow Infrastructure Post Merge 对纯文档/状态清理避免重复完整业务回归；
- setup-python 显式使用 `pyproject.toml`/锁定依赖文件作为 pip cache key；
- 明确禁止缓存 Scope、Secret Audit、Gate、Diff、当前 main 和 Post-Merge 结论。

### Gate

- 三种影响类别均有正反 Fixture；
- 混合改动总是升级到更高 Gate；
- Workflow/业务脚本变更不得被误判为 docs-only；
- E2E 可手工强制运行。

## W03｜平台状态与领域验收解耦

### 目标

Core 只理解：

```text
status
execution_status
acceptance.status
acceptance.domain
security_status
human_gate
post_merge
```

投研语义作为 Adapter/领域扩展，不再让 Core 字段名固定为 `research_acceptance_status`。

### 实现

- State schema v2；
- schema v1 `research_acceptance_status` 只读兼容并映射到：
  - `acceptance.domain = research`
  - `acceptance.status = <legacy value>`；
- 新模板和新任务使用 schema v2；
- `render_status`、`render_handoff`、验证器和 Finalizer 使用通用 Acceptance；
- `security_status` 与 Human Gate 独立校验；
- 旧已完成任务无需重写历史证据即可继续被验证。

### Gate

- schema v1/v2 双向读取矩阵；
- DONE 要求 execution=COMPLETED、acceptance=PASS、security=PASS、post_merge=PASS；
- 来源冲突可表现为 execution=COMPLETED、acceptance=REVIEW_REQUIRED，而不是程序失败。

## W04｜受管分支垃圾回收

### 目标

在不丢失审计证据的情况下回收：

```text
task/codex-*
codex/*
recovery/*
runtime/*
```

### 实现

- `scripts/devflow/branch_gc.py` 只处理明确前缀；
- 输入包括分支列表、开放 PR、默认分支、Active Tasks 与完成事件；
- 排除默认/保护/开放 PR/活动任务/未合并/无法证明归属的分支；
- `dry-run` 为默认；
- 任务完成后通过 `devflow_branch_gc` 精确传递 task/publish 分支；
- 删除前验证产品 Merge SHA 已在默认分支祖先链中；
- 所有删除操作幂等并写 Job Summary，不发邮件。

### Gate

- 纯函数 Fixture 覆盖可删、不可删、开放 PR、活动任务、非法前缀和重复运行；
- 首次生产运行只做 dry-run；
- 通过审计后再启用完成事件的精确分支删除。

## W05｜升级兼容测试

### 目标

防止执行器、State、Descriptor、Workflow 或模板升级后重新打开已完成任务、降低推理强度或破坏旧任务。

### 实现

- 增加版本化 Fixtures：
  - schema-v1 State；
  - schema-v1 Low Descriptor；
  - schema-v2 State；
  - schema-v2 XHigh Descriptor；
- 新增 `scripts/devflow/upgrade_compatibility.py`；
- 新增 `Devflow Upgrade Compatibility` Workflow；
- 验证：
  - v1 状态可读；
  - v1 Low 元数据不会降低生产 XHigh；
  - v2 新任务必须 XHigh；
  - 已完成任务不会被迁移器重新置为 RUNNING；
  - 新版本可生成确定性迁移预览，不直接覆盖历史证据。

### Gate

- 兼容矩阵全部 PASS；
- 迁移重复执行幂等；
- 未知 schema 版本 Fail Closed。

## W06｜收尾与采用建议

### 目标

- 合并前：State Consistency、影响分类、Devflow Tests、完整 Test；
- 由于本任务只改 Devflow/文档/Workflow，E2E 应由新的影响选择器判定为静默跳过真实抓取并产生 PASS Check；
- 合并后：exact-main Devflow Infrastructure Post Merge；
- 生成 W00–W06 result、FINAL_REPORT 与工程经验；
- 将新任务状态标记 DONE。

## PR 拆分

### PR-A｜Core 与文档

- XHigh 一致性；
- Context Budget；
- State schema v2 与通用 Acceptance；
- Change Impact 分类器；
- 单元与兼容 Fixtures；
- Policies/Runbooks/Templates。

### PR-B｜Workflow 与生命周期

- Test/E2E 影响感知执行；
- 依赖缓存键；
- Branch GC Workflow；
- Upgrade Compatibility Workflow；
- Post-Merge 选择逻辑；
- 最终结果与清理。

每个 PR 都必须从最新 `main` 同步并重新执行门禁。若 PR-A 已经足够安全地包含所有改动，可在不扩大风险的前提下合并为单个 PR；否则保持两 PR。

## 风险与控制

| 风险 | 控制 |
|---|---|
| docs-only 误判导致漏测 | 保守升级；未知路径按 product 处理 |
| XHigh 成本上升 | Context Budget、一次 Session、一次 Recovery Generation、短结构化输出 |
| Branch GC 误删 | 明确前缀、默认 dry-run、开放 PR/活动任务/祖先校验 |
| schema v2 破坏旧状态 | v1 只读兼容、Fixtures、幂等迁移预览 |
| 缓存陈旧结论 | 只缓存依赖，不缓存任何执行结论 |
| Workflow 改动自证不足 | 静态 Workflow 校验、Devflow Unit、PR Checks、exact-main Post-Merge |
