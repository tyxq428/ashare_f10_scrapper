# W06 计划：真实低风险 Codex 薄切片与无人值守闭环

## 目标

使用正式 `agent-runtime` 和 `openai/codex-action` 执行真实、局部且可确定验收的代码修复，并验证完整闭环：

```text
受信任务描述
→ Codex Thin Worker
→ Scope Guard 与 Targeted Gate
→ Secret-free Publish
→ Full Product Gate
→ 低风险自动合并
→ Exact-main Post-Merge
→ 最终完成通知
```

## 真实问题

`scripts/run_resilient_command.py` 在最后一次可重试失败后已经退出，但持久化报告可能仍显示 `RETRYING`。整体终态必须为 `FAILED`；attempt 级别仍可保留 `retryable: true`。

## 允许修改

- `scripts/run_resilient_command.py`
- `tests/test_resilient_fetch.py`

## Gate

- `resilient-command-targeted`；
- `repository-full`；
- `resilient-command-post-merge`。

## 自动恢复预算

- 当前任务代次 1 个 Codex Session；
- Targeted/Full/Post-Merge Gate 失败时最多新建 1 个受限 recovery generation；
- 基础设施类失败最多自动重跑失败 Job 3 次；
- 预算内恢复不写 Issue、不发邮件；
- 只有 Secret/权限、越界修改、业务决策或预算耗尽才通知。

## 完成标准

- Relay URL、hostname、Key 和模型 ID 无泄漏；
- Codex 只修改允许的两个文件；
- Targeted 和 Full Gate 通过；
- 任务描述明确 `risk_class=low`、`auto_merge=true`；
- 自动合并后 exact-main Post-Merge 通过；
- 不需要用户在 ChatGPT Web 输入“继续”；
- 整个任务完成时只产生 1 次 `[TASK][COMPLETED]`。
