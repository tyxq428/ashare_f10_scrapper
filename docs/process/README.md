# ChatGPT Web + GitHub Actions + Codex Thin Worker 执行规范

本目录将《通用高效率任务执行_标准化流程_v2.0.md》重构为可分层读取、可被 CI 校验的仓库规范。v2 的原则继续有效；本目录是后续维护的权威版本。

## 架构

```text
ChatGPT Web Supervisor
→ 任务合同、计划、业务决策和高风险变更
→ GitHub Actions Executor
→ 确定性预检、Gate、状态和Artifact
→ Auto Recovery Controller
→ 可恢复错误的分类、失败Job重跑和受限Codex Recovery Generation
→ Codex Thin Worker
→ 单次、窄范围代码修改
→ Product Gate / 低风险自动合并 / exact-main Post-Merge
→ 最终完成时才通知
```

## 分层

| 层级 | 位置 | 用途 |
|---|---|---|
| L0 | ChatGPT Project Instructions | 启动、恢复、角色边界 |
| L1 | `/AGENTS.md` | 仓库最高优先级规则 |
| L2 | scoped `AGENTS.md` | 目录和领域规则 |
| L3 | `policies/` | 长期政策与口径 |
| L4 | `runbooks/` | 可逐步执行的操作手册 |
| L5 | `templates/` | 状态、计划、结果、失败包和 Codex 任务模板 |
| L6 | `docs/implementation/<task-id>/` | 当前任务动态状态与证据 |
| L7 | workflows + `scripts/devflow/` | 确定性执行、自动恢复与门禁 |

## Policies

- [执行合同](policies/execution-contract.md)
- [状态与文档](policies/state-and-documentation.md)
- [监控与自动恢复](policies/monitoring-and-recovery.md)
- [质量门禁与自动合并](policies/gates-and-merge.md)
- [安全、Codex与恢复代次](policies/security-and-codex.md)
- [有价值通知](policies/notification-policy.md)
- [数据与研究语义](policies/data-and-research-semantics.md)

## Runbooks

- [启动新任务](runbooks/start-new-task.md)
- [恢复任务](runbooks/resume-task.md)
- [运行 Codex Thin Worker](runbooks/run-codex-thin-worker.md)
- [自动恢复与自动继续](runbooks/automatic-recovery.md)
- [处理真正的 Incident](runbooks/handle-incident.md)
- [Relay 健康检查](runbooks/relay-health-check.md)
- [合并后验证](runbooks/post-merge-validation.md)

## 核心纪律

1. 先定义完成，再执行。
2. 每个工作包先计划、后实现、再写结果。
3. 非错误、非人工决策不暂停。
4. 原始失败必须先自动分类和有限恢复，恢复预算内不通知用户。
5. 长任务必须可观测、可恢复、有限重试。
6. 业务状态与执行状态分离。
7. 确定性规则必须进入脚本或 CI。
8. Codex 只做单个已确定的修改，不负责总规划。
9. 只有显式批准的低风险任务才允许自动合并。
10. 未通过 exact-main Post-Merge 和 canonical closeout 不得写 100%。
11. `/ack` 只确认收到，不触发修复或继续。
