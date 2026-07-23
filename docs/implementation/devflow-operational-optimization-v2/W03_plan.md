# W03 Plan：Context Budget 与影响感知 Gate

## 目标

- XHigh 任务必须显式限制文件数、字节数和日志摘录；
- 禁止注入完整聊天历史和完整 SOP；
- 根据 `docs_only / devflow_only / product` 选择最小充分 Gate；
- 只缓存依赖，不缓存 Scope、Secret、Gate 或 Post-Merge 结论。
