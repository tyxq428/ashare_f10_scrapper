# W02 结果：付费 Relay 探针与 Secret Audit 边界

```yaml
status: PASS
relay_default_mode: configuration_only
relay_default_responses_requests: 0
paid_probe_exact_confirmation_required: true
paid_probe_purpose_required: true
paid_probe_requests_per_dispatch_max: 1
relay_health_in_auto_recovery: false
relay_paid_probe_automatic_retries: 0
secret_audit_automatic_trigger: false
secret_audit_source_validation_before_environment: true
secret_audit_required_source_workflow: Codex One-Time Activation
codex_calls: 0
responses_paid_probes_during_implementation: 0
```

Relay Health 仍可在用户明确要求时执行一次付费协议探针，但常规配置检查不会发送请求。Secret Audit 只有在零 Secret Job 验证真实一次性 Activation Run 后才会绑定 `agent-runtime`。
