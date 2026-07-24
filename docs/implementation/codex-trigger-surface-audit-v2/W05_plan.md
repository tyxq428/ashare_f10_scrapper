# W05 计划：Exact-main 与最终收尾

## 完成条件

```yaml
legacy_task_branches_quarantined: true
historical_workflow_rerun_model_paths: 0
relay_default_paid_requests: 0
relay_automatic_retries: 0
secret_audit_automatic_triggers: 0
permanent_direct_model_paths: 0
codex_policy: disabled
codex_calls: 0
responses_paid_probes_during_task: 0
full_test: PASS
real_e2e_688521: PASS
exact_main: PASS
canonical_state: DONE
```

合并后必须在精确 `main` 重跑入口扫描、Devflow/Upgrade、完整 Test 和真实 E2E，生成最终报告并删除一次性 Workflow。
