# W01 结果：分层 SOP 与 AGENTS

## 状态

```yaml
phase: W01
status: COMPLETED
last_successful_step: layered_instruction_tree_materialized
next_action: W02_canonical_state
human_intervention_required: false
```

## 结果

- 建立根级和四个 Scoped `AGENTS.md`；
- 建立七份 Policies、六份 Runbooks 和标准 Templates；
- 提供可复制到 ChatGPT Project 的短 Project Instructions；
- v2 的任务合同、批量执行、监控、恢复、质量、人工介入和复盘原则继续保留；
- 新增 Web/Actions/Codex 角色边界、Secret 分离、valuable-only 通知和 post-merge 阻断规则；
- 动态任务状态不进入长期指令，降低版本漂移和固定 Token 成本。
