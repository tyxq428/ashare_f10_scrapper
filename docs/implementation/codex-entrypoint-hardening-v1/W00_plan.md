# W00 计划：基线与全模型入口清单

## 目标

- 冻结当前 `main` SHA；
- 建立 `.devflow/codex-entrypoints.yaml`；
- 扫描 Workflow、Action、脚本和文档中的模型入口关键字；
- 将唯一允许入口限定为 `manual_one_time_executor`，且当前实现仍为无模型资格检查；
- 证明 Product Gate 是当前唯一残留自动 Dispatch 路径；
- 本阶段模型调用次数为 0。

## 验收

```yaml
policy_mode: disabled
model_action_references_in_runtime: 0
automatic_dispatch_paths_inventory_complete: true
current_residual_product_gate_dispatch_identified: true
codex_calls: 0
```
