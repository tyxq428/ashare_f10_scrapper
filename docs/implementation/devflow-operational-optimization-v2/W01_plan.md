# W01 Plan：干净重建与熔断同步

## 目标

从已冻结的最新 main 建立干净分支，只迁移仍有效的优化实现，并同步 BLOCKED 终态和 State Consistency Web-only 修复。

## 验收

- 不直接 Rebase 旧 PR 的 99 个提交；
- 不保留临时 Workflow、重复 Action 或自动 Codex 路径；
- 所有修复由 ChatGPT Web 和确定性脚本完成。
