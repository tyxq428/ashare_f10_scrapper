# W01 计划：删除 Product Gate 自动 Codex Recovery

## 实施

- 删除 Full Gate 失败后的 `recovery_task.py`、Recovery 分支和 `codex-task.yml` Dispatch；
- 失败统一产生 `PRODUCT_GATE_WEB_REPAIR_REQUIRED`；
- 保留 Scope Fail Closed、Full Gate、受控合并与 Post-Merge；
- Validator 和测试禁止 Product Gate 出现任何自动模型路径。

## 验收

`product_gate_codex_recovery=false`，`automatic_dispatch_paths=0`，Codex 调用为 0。
