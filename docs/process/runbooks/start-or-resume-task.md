# Runbook: start or resume a task

## Start

1. Read root and scoped Agent instructions.
2. Audit latest `main`, open PRs, existing active tasks, and shared files.
3. Create a unique task ID and branch.
4. Commit `W00_plan.md` before other implementation.
5. Create the contract, master plan, canonical state, handoff, decisions, and Draft PR.
6. Run the baseline Gate.
7. Continue stage by stage unless a defined human gate occurs.

## Resume

1. Read `ACTIVE_TASKS.yaml` and the active `task_state.yaml`.
2. Verify branch head, PR state, latest Checks, and `last_product_commit_sha` ancestry.
3. Read `HANDOFF.md` and current stage plan.
4. Reconcile stale generated status from canonical state.
5. If a Workflow is still running, observe it; do not duplicate it.
6. If a failure bundle exists, classify it before retrying.
7. Continue the stored `next_action` without relying on chat history.

## Transfer to a new conversation

Use: “按仓库执行规范恢复当前活动任务；从 canonical state、HANDOFF、最新 PR、HEAD 和 Checks 恢复，非真实人工门槛直接继续。”
