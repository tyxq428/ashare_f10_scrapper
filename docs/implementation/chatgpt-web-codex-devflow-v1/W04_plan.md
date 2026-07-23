# W04 计划：Reusable Codex、Private Relay、Secret Audit 与 Incident

## 目标

把 `temp_test` 已验证的安全链路迁移到正式仓库，并抽象为可复用、最小权限、单 Session 的生产组件。

## 实施范围

### Scripts

- `endpoint_utils.py`
- `private_responses_forwarder.py`
- `relay_health_check.py`
- `secret_audit.py`
- `notify_incident.py`
- `validate_workflows.py`

### Workflows

- `_reusable-codex-thin-worker.yml`
- `codex-task.yml`
- `devflow-state-consistency.yml`
- `devflow-secret-audit.yml`
- `devflow-incident.yml`
- `devflow-relay-health.yml`
- `devflow-post-merge.yml`

## 安全架构

```text
Environment Secrets
→ read-only Codex Job
→ localhost no-log forwarder
→ openai/codex-action pinned SHA
→ deterministic scope/result checks
→ secret-scanned minimal patch artifact
→ separate secret-free write Job
→ trusted Gate Profile
→ push work branch
→ ChatGPT Web creates/updates PR
```

## 触发规则

- 正式 Codex Workflow 支持人工 `workflow_dispatch`；
- 为 ChatGPT Web 连接器提供仅限 owner、特定 request 路径和特定分支前缀的 trusted push 入口；
- 不接受 Fork PR、Issue/comment 或 `pull_request_target` 触发；
- Relay Health 只手工运行或配置变化后运行；
- Secret Audit 使用独立 `workflow_run` 终态审计；
- Incident 只在高价值状态产生 Issue/mention。

## Token 控制

- `effort: low` 显式固定；
- 每个任务一个 Codex Session；
- 不在 Codex Session 内跑完整 Test；
- 不自动开启第二 Session；
- 普通任务不重复 T1 健康握手。

## Gate

- Python compile、Ruff 和 devflow tests；
- Workflow YAML 静态解析；
- 禁止危险触发器和权限组合；
- Action 引用固定 40 位 SHA；
- Secret 名称可见但 Secret 值/URL/hostname/模型值不可见；
- Incident 去重与 PASS 静默测试。

## 恢复入口

```yaml
phase: W04
checkpoint: W04_PLAN_COMMITTED
next_action: implement_reusable_workflows_and_security_scripts
human_intervention_required: false
```
