# W04 计划：Reusable Codex 与安全工作流

## 目标

建立正式可复用的 Codex Thin Worker、任务入口、状态一致性、Relay Health、Secret Audit、Incident 和 post-merge 工作流。

## 安全结构

```text
Environment Secrets
→ read-only Codex Job
→ localhost-only no-log Responses Forwarder
→ one Codex Session / low effort
→ Scope Guard + G1 + Secret Audit
→ secret-free Patch + Manifest Artifact
→ separate contents:write Publish Job
→ ChatGPT Web creates/reviews PR
```

## 验收

- URL/Key/模型从不作为明文参数进入 Public 内容；
- 新第三方 Actions 固定完整 SHA；
- Codex 修改越界、Gate 失败或 Secret 命中不发布；
- Publish Job 不引用 Environment；
- Incident 仅通知四类高价值状态；
- Relay Health 不在每个任务重复执行；
- 单元测试和 Workflow 静态检查通过。

## 恢复入口

```yaml
phase: W04
checkpoint: W04_PLAN_COMMITTED
next_action: implement_and_validate_workflows
human_intervention_required: false
```
