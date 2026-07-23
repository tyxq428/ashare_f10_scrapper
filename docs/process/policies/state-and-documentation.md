# 状态与文档政策

## 唯一状态源

每个活动任务必须有：

```text
docs/implementation/<task-id>/task_state.yaml
```

该文件使用 JSON 语法（JSON 是 YAML 的严格子集），以便标准库确定性解析。PR 描述、`STATUS.md`、`HANDOFF.md` 和聊天摘要不得成为独立状态源。

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

- `Wxx_plan.md` 必须先于实现提交。
- 只有 Gate 通过后才能写 `Wxx_result.md`。
- 结果必须包含修改范围、提交 SHA、Workflow Run、Gate、偏差、遗留问题和下一动作。
- `DONE` 必须同时满足：所有必做工作包完成、交付物存在、`post_merge.status == PASS`。

## 提交身份

避免状态文件自引用当前 HEAD。状态保存：

- `base_sha_at_start`；
- `last_product_commit_sha`；
- `last_state_commit_sha`（可为空或滞后）；
- `state_revision`。

验证规则是 `last_product_commit_sha` 必须是当前分支 HEAD 的祖先；允许产品提交之后存在纯状态和文档提交。

## 恢复读取顺序

活动任务索引 → canonical state → GitHub Checks → 分支/PR → HANDOFF → 当前计划/结果 → 聊天历史。
