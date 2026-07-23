# Runbook：自动恢复、自动继续与通知升级

## 输入

`Devflow Auto Recovery` 读取：

- Workflow name、Run ID、run attempt 和 conclusion；
- Job/Step 名称与 conclusion；
- Context、Scope、Secret、Runtime 和 Codex 结构化摘要；
- 可用时的 immutable `.agent/current_task.yaml`；
- canonical recovery budget。

不读取或输出 Relay URL、Key、模型 ID、完整环境、Prompt、源代码全文或原始 HTTP 日志。

## 分类结果

| Action | 系统动作 | 用户通知 |
|---|---|---|
| `NOOP` | 无动作 | 否 |
| `RETRY` | 只重跑已验证的基础设施失败 Job | 否 |
| `CODEX_REPAIR` | 基于有效 immutable scope 创建一个 schema-v2 XHigh Recovery Generation | 否 |
| `HUMAN_REQUIRED` | 停止并给出唯一人工动作 | 是 |
| `SECURITY_BLOCKED` | 阻止发布和自动恢复 | 是 |
| `INTERRUPTED` | Codex 明确 BLOCKED、预算耗尽、无安全 scope 或无法分类 | 是 |
| `COMPLETED` | 自动收尾并通知 | 是，1次 |

生产 Workflow 不执行 `RETRY_CODEX`。每个 Generation 只允许一次模型 Session；相同 Descriptor、相同证据和相同失败不得自动重复调用模型。

## Context Budget

`context-budget.json` 在 Codex 分类前读取。超预算时：

```text
CONTEXT_BUDGET_EXCEEDED
→ 不重试Codex
→ 不降低推理强度
→ 要求缩小允许文件或拆分任务
```

这是任务范围门槛，不是网络或模型故障。

## 基础设施恢复

可重试范围：

- `cancelled / timed_out / stale / startup_failure`；
- checkout、setup、依赖安装；
- Artifact 上传/下载；
- Relay 临时 transport/protocol 错误。

在预算内只调用 `rerun-failed-jobs`，不创建 Issue 评论。基础设施判断优先于 Codex 阶段判断，因此 checkout 等失败仍可静默重跑。

## Codex Circuit Breaker

- `codex-result.status == BLOCKED`：`CODEX_DECLARED_BLOCKED`，禁止相同 Generation 重跑；
- `SUCCESS` 但 `tests_passed != true`：`CODEX_RESULT_UNVERIFIED`；
- 无可发布结构化结果：`CODEX_EXECUTION_FAILED_NO_RETRY`；
- State Consistency 没有 immutable Task Descriptor：`STATE_REPAIR_SCOPE_UNAVAILABLE`，禁止合成通用 scope；
- 只有 Full/Post-Merge 等确定性 Gate 失败且存在原始批准 scope 时，才可创建一个新的 Recovery Generation；
- 新 generation 使用 schema v2/XHigh，继承 allowed files、forbidden patterns、Context、Gate、risk class 和 auto-merge；
- 不扩大上下文，不修改 Workflow/Secrets；
- schema-v1 Low 只读兼容，不会降低 Recovery 运行强度。

## Product Gate

1. 读取 immutable Descriptor 并验证 `expected_base_sha` 祖先关系；
2. 使用 Merge Base 校验候选新增路径；
3. Scope 失败进入 `SECURITY_BLOCKED`；
4. Scope PASS 后执行 Full Gate；
5. Full Gate 失败且有预算与有效 scope 时创建 XHigh Recovery Generation；
6. 通过且批准低风险自动合并时固定 Git 身份；
7. `main` 推进时 rebase，再跑 Scope/Full Gate；
8. 使用受控 merge commit 合并；
9. 显式发送 `devflow_post_merge`。

缺少 Git identity 是机械配置，不是人工门槛。只有 conflict、branch protection、权限或远端拒绝才是 `AUTO_MERGE_BLOCKED`。

## Post-Merge 与分支生命周期

Post-Merge 在 exact `main` 上执行。成功时：

- 更新 canonical state；
- 生成阶段结果和最终报告；
- 验证全部活动/已索引任务状态；
- 运行 Upgrade Compatibility；
- 提交收尾文档；
- 发送一次 `COMPLETED`；
- 关闭 task-control Issue；
- 派发 `devflow_branch_gc`，第一阶段固定 `execute=false` dry-run。

分支删除不属于恢复动作；它必须由独立 fail-closed 规划器处理。

## 影响感知 Gate

普通文档和 Devflow 基础设施变更不需要重复真实产品 E2E。`change_impact.py` 选择 docs/devflow/product Gate；未知路径始终升级为 product。依赖缓存只加速安装，不缓存任何安全或验收结论。

## 人工通知

只有自动恢复不再安全或预算耗尽时才通知。`/ack` 不触发动作。用户完成外部配置、权限或业务决定后，使用 `/resume` 或向 ChatGPT Web 提供新事实。
