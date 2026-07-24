# ChatGPT Web + GitHub Actions 执行规范

本目录将《通用高效率任务执行_标准化流程_v2.0.md》重构为可分层读取、可由 CI 校验的仓库规范。v2 原则继续有效；本目录是后续维护的权威版本。

## 架构

```text
ChatGPT Web Supervisor
→ 任务合同、计划、实现、诊断、业务决策和高风险变更
→ GitHub Actions Executor
→ Context / Scope / State / Secret / Gate
→ Zero-model Auto Recovery
→ 只重试受信任的普通零模型基础设施错误
→ Product Gate / 低风险自动合并 / exact-main Post-Merge
→ 最终完成通知 / 受管分支GC dry-run
```

Codex 不属于默认执行链。仓库级 Policy 保持 `disabled`；常驻 `Codex Task` 只做零 Token候选复核。未来只有用户针对一个具体任务再次明确授权、受信任真实复现和一次性 Grant全部通过，并由独立受审 Activation PR临时加入模型 Job时，才允许一次 XHigh Session。

历史 Workflow Re-run和 Relay付费探针也属于模型费用执行面：

- `Devflow Legacy Codex Rerun Audit` 隔离所有历史 `task/codex-*` 分支；
- `Devflow Relay Health` 默认发送 0 个请求；
- 付费 Relay探针必须人工精确确认且永不自动重跑；
- Secret Audit只审计经验证的一次性 Activation Run。

## 分层

| 层级 | 位置 | 用途 |
|---|---|---|
| L0 | ChatGPT Project Instructions | 启动、恢复、角色边界 |
| L1 | `/AGENTS.md` | 仓库最高优先级规则 |
| L2 | scoped `AGENTS.md` | 目录和领域规则 |
| L3 | `policies/` | 长期政策与口径 |
| L4 | `runbooks/` | 可逐步执行的操作手册 |
| L5 | `templates/` | 状态、计划、结果、失败包和任务模板 |
| L6 | `docs/implementation/<task-id>/` | 动态状态与证据 |
| L7 | workflows + `scripts/devflow/` | 确定性执行、恢复与门禁 |

## Machine-readable control

- `.devflow/codex-policy.yaml`：仓库级模型总开关；
- `.devflow/codex-entrypoints.yaml`：唯一允许入口、可信控制、历史 Re-run隔离、付费探针和一次性 Activation边界；
- `.devflow/codex-grants/`：一次性 Grant规范；
- `docs/implementation/CODEX_USAGE_LEDGER.json`：`RESERVED / CONSUMED` 用量账本；
- `scripts/devflow/validate_codex_entrypoints.py`：全仓自动模型与付费探针路径扫描；
- `scripts/devflow/legacy_codex_branch_audit.py`：远端历史任务分支 Re-run隔离审计。

## Policies

- [执行合同](policies/execution-contract.md)
- [状态与文档](policies/state-and-documentation.md)
- [监控与自动恢复](policies/monitoring-and-recovery.md)
- [质量门禁与自动合并](policies/gates-and-merge.md)
- [影响感知 Gate 与安全缓存](policies/cache-and-impact-gates.md)
- [安全、Codex与一次性 Activation](policies/security-and-codex.md)
- [有价值通知](policies/notification-policy.md)
- [数据与研究语义](policies/data-and-research-semantics.md)

## Runbooks

- [启动新任务](runbooks/start-new-task.md)
- [恢复任务](runbooks/resume-task.md)
- [一次性 Codex Thin Worker Activation](runbooks/run-codex-thin-worker.md)
- [零模型自动恢复与自动继续](runbooks/automatic-recovery.md)
- [处理真正的 Incident](runbooks/handle-incident.md)
- [Relay 健康检查](runbooks/relay-health-check.md)
- [合并后验证](runbooks/post-merge-validation.md)
- [受管分支垃圾回收](runbooks/branch-garbage-collection.md)
- [升级兼容](runbooks/upgrade-compatibility.md)

## 核心纪律

1. 先定义完成，再执行；
2. 每个工作包先计划、后实现、再写结果；
3. 非错误、非人工决策不暂停；
4. 原始失败先确定性分类；只有普通零模型基础设施错误可有限重试；
5. 长任务可观测、可恢复、有限重试；
6. 平台执行状态与领域验收状态分离；
7. 确定性规则进入脚本或 CI；
8. Codex 默认禁用，ChatGPT Web 是常规实现和修复路径；
9. 未知失败、Full Gate和 Post-Merge失败不得自动进入 Codex；
10. 任务分支是 data-only，Policy、Eligibility和 Gate来自精确默认分支 SHA；
11. Context Budget、受信任复现和一次性 Grant必须在任何模型步骤前通过；
12. 模型 Job一旦预占 Grant即不可重跑；
13. 历史模型 Run的原任务分支必须持续隔离；
14. Relay付费探针必须人工精确确认且不可自动重跑；
15. 只缓存依赖，不缓存 Scope、安全、Gate或 Post-Merge结论；
16. 只有显式批准的低风险任务才允许自动合并；
17. 未通过 exact-main Post-Merge、升级兼容和 canonical closeout不得写 100%；
18. 受管分支 GC默认 dry-run；
19. `/ack` 只确认收到，不触发修复或继续。
