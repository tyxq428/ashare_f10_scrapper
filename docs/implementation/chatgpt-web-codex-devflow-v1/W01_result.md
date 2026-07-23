# W01 结果：分层 SOP、Policies、Runbooks 与 Templates

## 状态

```yaml
phase: W01
status: COMPLETED
next_action: W02_canonical_state_and_consistency_engine
human_intervention_required: false
```

## 完成内容

- 建立根级与四个 Scoped `AGENTS.md`，将高频强制规则放到最近的执行范围；
- 将长期规则拆成执行状态、监控恢复通知、Gate 安全合并、数据研究语义四类 Policy；
- 建立启动/恢复、Codex Thin Worker、Incident/post-merge、Relay Health 四个 Runbook；
- 建立任务状态、活动任务、合同、主计划、阶段计划/结果、Handoff、Decisions、Failure Bundle 和 Codex Task 模板；
- 建立 ChatGPT Project Instructions 建议文本；
- 建立 SOP v2 来源映射，明确 v2 原则未废弃且未来不维护两份冲突的完整 SOP。

## 验收

- 根级 Agent 指令保持短小，不复制 42KB SOP；
- 动态 Run ID、阶段和临时错误未进入长期指令；
- Secret、Endpoint、hostname、Key 和模型值未写入文档；
- 新任务和恢复任务可以只读取分层入口和 canonical state；
- Codex 只需加载作用域规则和当前任务包。

## Gate

`W01-DOCUMENT-LAYERING: PASS`
