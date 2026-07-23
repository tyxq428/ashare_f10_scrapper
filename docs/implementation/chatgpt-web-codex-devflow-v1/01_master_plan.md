# 主计划：W00—W08

| 阶段 | 目标 | 主要 Gate |
|---|---|---|
| W00 | 基线、权限与安全预检 | G0 baseline |
| W01 | 分层 SOP 与 AGENTS | 文档/链接/冲突检查 |
| W02 | Canonical state、模板和一致性引擎 | G0 state |
| W03 | Gate profiles、Failure Bundle 和范围控制 | G1 devflow |
| W04 | Reusable Codex、Relay、Secret Audit、Incident | Workflow 安全检查 |
| W05 | PR-A 全量验证、合并与 post-merge | G0/G1/G2/G5 |
| W06 | 正式仓库真实低风险 Codex 薄切片 | Scope/G1/G2/G5 |
| W07 | 渐进迁移政策和前三个任务指标 | 迁移矩阵 |
| W08 | 最终报告、经验沉淀和清理 | 全部终态 Gate |

## 连续执行政策

阶段 Gate 通过且不存在真实人工门槛时，自动进入下一阶段。可重试网络和平台错误只重试失败范围。机械错误使用同版本工具修复。重复逻辑失败、权限、安全或业务决策才进入人工状态。

## Pull request 策略

- PR-A：W00—W05，分层流程和执行基础设施；
- PR-B：W06，Codex Thin Worker 修改真实低风险缺陷；
- W07—W08 作为验证结果和收尾文档落入对应已验证分支或独立文档提交。

## 通知政策

只通知 `COMPLETED`、`INTERRUPTED`、`HUMAN_REQUIRED`、`SECURITY_BLOCKED`。中间 PASS、审计 PASS、缓存命中、分支 Push 和 Draft PR 更新静默。
