# W04 Plan：状态解耦与 Branch GC

## 目标

- 使用 Schema v2 分离 `execution_status`、领域 `acceptance` 和 `security_status`；
- 保留 Schema v1 只读兼容；
- Branch GC 仅处理受管前缀，默认 dry-run，无法证明安全时保留。
