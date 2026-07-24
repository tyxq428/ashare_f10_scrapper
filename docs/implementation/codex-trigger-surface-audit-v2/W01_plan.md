# W01 计划：历史 Codex Workflow Re-run 隔离

## 实施

1. 新增 `legacy_codex_branch_audit.py`；
2. 使用 `git ls-remote` 枚举所有 `refs/heads/task/codex-*`；
3. 读取开放 PR head 列表；
4. 对无开放 PR 的历史任务分支：
   - 删除 `.agent/current_task.yaml`；
   - 写入 `LEGACY_CODEX_RERUN_QUARANTINED.json`；
   - 将 Composite Action替换为默认分支的禁用版本；
   - fast-forward commit并Push；
5. 生成只含分支名和状态的审计报告；
6. 新增默认分支永久只读 Workflow，定期和手工审计。

## Fail Closed

- 有开放 PR：不修改，记录并失败；
- 分支不可 fast-forward Push：停止并报告；
- 隔离后仍有 Descriptor：失败；
- Action 中存在 `openai/codex-action` 或缺少禁用标记：失败；
- 隔离过程不得访问 `agent-runtime`。
