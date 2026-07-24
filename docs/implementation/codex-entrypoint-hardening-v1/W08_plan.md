# W08 计划：验证、合并与 Exact-main 收尾

## 门禁

1. Codex Entrypoint 静态扫描；
2. State Consistency、Workflow、Docs、Ruff、Devflow pytest；
3. Upgrade Compatibility；
4. 完整产品 Test；
5. 真实 688521 E2E；
6. 合并后 exact-main 再验证。

## 合并前证据

一次性零模型验证 Run `30058774833` 已在分支产品与执行代码上完成：

- Codex Policy / Entrypoint Scan：PASS；
- Devflow、状态、文档、Ruff、pytest 与升级兼容：PASS；
- 完整产品回归：PASS；
- 真实 688521 E2E：PASS；
- Codex、Relay 与 `agent-runtime` 调用：0。

该 Run 成功后仅提交阶段结果和删除一次性 Workflow。当前用户提交用于重新触发常规 PR Checks；不会重复模型或 Relay 操作。

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
