# W08 计划：验证、合并与 Exact-main 收尾

## 门禁

1. Codex Entrypoint 静态扫描；
2. State Consistency、Workflow、Docs、Ruff、Devflow pytest；
3. Upgrade Compatibility；
4. 完整产品 Test；
5. 真实 688521 E2E；
6. 合并后 exact-main 再验证。

## 完成条件

```yaml
codex_calls: 0
policy_mode: disabled
automatic_codex_dispatch_paths: 0
product_gate_codex_recovery: false
model_job_rerunnable: false
unknown_reason_codex_candidate: false
grant_ttl_minutes_max: 60
all_pre_merge_gates: PASS
exact_main: PASS
canonical_state: DONE
```
