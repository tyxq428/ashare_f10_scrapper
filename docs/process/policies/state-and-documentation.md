# 状态与文档政策

## 唯一状态源

每个任务必须有：

```text
docs/implementation/<task-id>/task_state.yaml
```

该文件使用 JSON 语法（JSON 是 YAML 的严格子集），以便标准库确定性解析。PR 描述、`STATUS.md`、`HANDOFF.md` 和聊天摘要不得成为独立状态源。

`docs/implementation/ACTIVE_TASKS.yaml` 是任务索引；State Consistency 必须验证索引中的全部任务，而不是只验证某个固定任务 ID。

## State schema v2

平台核心只理解：

```yaml
status: RUNNING | VERIFYING | WAITING_HUMAN | BLOCKED | DONE
execution_status: PENDING | RUNNING | COMPLETED | FAILED | BLOCKED
acceptance:
  domain: generic | research | <adapter-domain>
  status: PENDING | PASS | REVIEW_REQUIRED | FAIL
  reason_code: null | <domain-code>
  details_path: null | <evidence-path>
security_status: PENDING | PASS | BLOCKED | FAIL
human_gate: ...
post_merge: ...
```

领域口径不得被写死在 Core 字段名中。例如真实来源冲突可以表示为：

```yaml
execution_status: COMPLETED
acceptance:
  domain: research
  status: REVIEW_REQUIRED
  reason_code: SOURCE_CONFLICT
```

这不是程序崩溃。

schema v1 的 `research_acceptance_status` 保持只读兼容，并映射到 `acceptance.domain=research`；新任务和新模板使用 schema v2。

## 完成条件

`DONE` 必须同时满足：

- `execution_status == COMPLETED`；
- `acceptance.status == PASS`；
- `security_status == PASS`；
- `post_merge.status == PASS`；
- `human_gate.required == false`；
- 当前阶段等于最后完成阶段；
- 必需计划、结果和最终报告存在。

## 必需文件

- `00_contract.md`
- `01_master_plan.md`
- `task_state.yaml`
- `STATUS.md`
- `HANDOFF.md`
- `DECISIONS.md`
- 每阶段 `Wxx_plan.md`
- 已完成阶段 `Wxx_result.md`
- 最终 `FINAL_REPORT.md`

## 阶段规则

- `Wxx_plan.md` 必须先于实现提交；
- 只有 Gate 通过后才能写 `Wxx_result.md`；
- 结果包含修改范围、提交 SHA、Workflow Run、Gate、偏差、遗留问题和下一动作；
- 平台生命周期与项目工作包编号相互独立，Core 不推断业务含义。

## 提交身份

避免状态文件自引用当前 HEAD。状态保存：

- `base_sha_at_start`；
- `last_product_commit_sha`；
- `last_state_commit_sha`（可为空或滞后）；
- `state_revision`。

`last_product_commit_sha` 必须是当前分支 HEAD 的祖先；允许产品提交之后存在纯状态和文档提交。

## 升级与恢复

- 未知 schema 版本 Fail Closed；
- 迁移先生成幂等预览，不直接覆盖历史证据；
- 已完成任务不得因升级重新变为 RUNNING；
- 恢复读取顺序：任务索引 → canonical state → GitHub Checks → 分支/PR → HANDOFF → 当前计划/结果 → 聊天历史。
