# W05 计划：Codex 最小必要性与正向 Allowlist

## 实施

仅允许以下 Reason Code 成为候选：

- `LOCAL_IMPLEMENTATION_DEFECT`；
- `LOCAL_TEST_GAP`；
- `BOUNDED_PURE_REFACTOR`。

同时必须有 `web_resolution_assessment`：已由 ChatGPT Web 尝试分析、当前会话不适合完成，并明确记录 `LOCAL_ITERATIVE_TOOL_LOOP` 或用户明确要求独立后台 Worker。未知原因、单文件简单修改、机械错误和 Full/Post-Merge 失败均回到 ChatGPT Web。

## 验收

未知 Reason Code 的候选结果必须为 false；没有 Web 必要性评估时必须拒绝。
