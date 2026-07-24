# W02 计划：付费 Relay 探针与 Secret Audit 边界

## 目标

- Relay Health 默认不发送网络请求；
- 真实 Responses 探针必须由仓库所有者输入精确确认短语和非空目的；
- Auto Recovery 不监听 Relay Health，不得自动重跑付费请求；
- Secret Audit 在绑定 `agent-runtime` 前，先用零 Secret Job 验证：
  - 精确 Source Run ID；
  - Workflow 名称为 `Codex One-Time Activation`；
  - 事件为人工 `workflow_dispatch`；
  - 分支为 `main`；
  - 日志含绑定 Activation ID 的模型启动标记。

## Gate

```yaml
relay_default_requests: 0
relay_paid_probe_confirmation_required: true
relay_auto_retry: false
secret_audit_auto_trigger: false
secret_environment_before_source_validation: false
codex_calls: 0
```
