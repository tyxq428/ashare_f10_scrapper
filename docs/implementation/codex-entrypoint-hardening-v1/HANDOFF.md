# HANDOFF

## 当前检查点

- 基线：`3dd0075c83651d73677ecf8105946ae34bad362e`；
- 分支：`feature/codex-entrypoint-hardening-v1`；
- 阶段：W00；
- Codex Policy：`disabled`；
- 本任务 Codex 调用：0。

## 恢复顺序

1. 读取 `task_state.yaml`；
2. 读取 `01_master_plan.md` 和当前 `W00_plan.md`；
3. 检查分支 HEAD、开放 PR 和 GitHub Checks；
4. 继续全路径清单、静态 Guard 与 Product Gate 自动 Dispatch 删除；
5. 不得创建或重跑任何 Codex Task。
