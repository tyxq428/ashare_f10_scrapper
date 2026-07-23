# Runbook：合并后验证

1. 记录合并 SHA，确认 `main` 指向预期产品提交。
2. 在新的独立运行中执行 G5；不得仅引用合并前 PASS。
3. 基础设施 PR 至少执行状态一致性、devflow 单元测试、Workflow 静态安全和现有 Test。
4. 产品 PR 执行受影响的完整 Test、真实薄切片和必要产品 E2E。
5. 若出现网络临时错误，分类后只重跑失败 Job；若暴露代码缺口，建立独立热修复分支/PR。
6. G5 失败时 canonical state 保持 `POST_MERGE_BLOCKED`，不得写完成度 100%。
7. G5 全部通过后，写最终结果、更新工程经验、清理临时分支/Workflow/Artifact，并仅发送一次 `[TASK][COMPLETED]`。
