# W03 计划：平台状态与领域验收解耦

## 目标

将 Devflow Core 从固定 `research_acceptance_status` 解耦，支持通用领域验收，同时只读兼容历史 schema v1。

## 实施范围

- State schema v2：`acceptance` 与 `security_status`；
- `state_model.py`、`render_task_docs.py`、State 模板；
- `validate_state.py --all-active`；
- v1/v2 正反回归。

## 验收

- 执行成功、领域需复核可以同时表达；
- schema-v1 映射到 `acceptance.domain=research`；
- schema-v2 `DONE` 要求 execution/acceptance/security/post-merge 全部 PASS；
- 未知 schema Fail Closed；
- State Consistency 验证 `ACTIVE_TASKS` 中所有任务。
