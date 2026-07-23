# W01 计划：分层 SOP、Policies、Runbooks 与 Templates

## 目标

将 SOP v2 的长期规则拆分为短而强制的 Agent 指令、稳定 Policies、可操作 Runbooks、标准 Templates 和动态任务状态，避免每次对话或 Codex Session 重复加载整份长文档。

## 实施范围

- 根级与 Scoped `AGENTS.md`；
- `docs/process/policies/`；
- `docs/process/runbooks/`；
- `docs/process/templates/`；
- `docs/process/archive/` 中的 v2 来源快照说明；
- ChatGPT Project Instructions 建议文本；
- 文档索引和链接校验约定。

## 设计原则

1. 高频强制规则靠近执行位置；
2. 长期解释性政策只保留一个权威来源；
3. 当前任务事实不写入长期指令；
4. Codex 只加载根级、作用域指令和当前任务包；
5. 模板和确定性脚本代替重复自然语言；
6. v2 不废弃，其原则被逐项映射并保留来源说明。

## 验收标准

- 根 `AGENTS.md` 简短且不复制完整 SOP；
- Scoped 指令不削弱根安全约束；
- Policies、Runbooks、Templates 的职责不重叠；
- 所有索引路径真实存在；
- 不包含动态 Run ID、真实 Secret、Endpoint、hostname 或模型值；
- 新任务和恢复任务无需再次粘贴 SOP 全文。

## 恢复入口

```yaml
phase: W01
checkpoint: W01_PLAN_COMMITTED
next_action: create_policies_runbooks_templates_and_archive_map
human_intervention_required: false
```
