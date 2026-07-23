# Runbook：恢复活动任务

1. 不依赖聊天历史；读取 `ACTIVE_TASKS.yaml`。
2. 读取当前任务 `task_state.yaml` 和 `HANDOFF.md`。
3. 核对分支 HEAD、PR、最新 Checks、Artifact 和未确认 Incident。
4. 确认 `last_product_commit_sha` 仍是当前 HEAD 的祖先，状态没有被并行分支覆盖。
5. 若 Workflow 仍在运行，只记录 Run ID 和心跳，不重复派发。
6. 若已成功，验证 Gate 证据，写阶段结果并进入下一计划。
7. 若失败，先分类：基础设施可有限定向重试；代码/数据/安全问题生成 Failure Bundle；业务问题进入 `HUMAN_REQUIRED`。
8. 更新 canonical state 和 HANDOFF，再继续执行。不得重新处理已成功工作或无理由从头运行。
