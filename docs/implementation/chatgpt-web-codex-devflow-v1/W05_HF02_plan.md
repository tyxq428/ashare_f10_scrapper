# W05_HF02 计划：任务控制 Issue 单例化与通知竞态修复

## 背景

`Devflow Incident` 在多个 `workflow_run` 几乎同时结束时，会由多个独立运行先后查询开放 Issue。若它们都在第一个 Issue 创建前完成查询，就会各自创建同名控制 Issue，产生 #31 与 #32 两个通知通道。

## 目标

1. 将 #32 固定为任务 `chatgpt-web-codex-devflow-v1` 的唯一 canonical 控制 Issue；
2. 关闭 #31，并标记为 duplicate；
3. 在 canonical state 中持久化 `notification.control_issue_number`；
4. 让 Incident Workflow 优先使用 canonical issue number，而不是每次通过标题猜测；
5. 增加同任务串行保护和事件标记去重；
6. 修复当前热修复分支中 `TaskState` 未暴露 `pull_request` 导致的回归测试失败；
7. 保证普通阶段、PASS 和审计通过仍保持静默。

## 允许修改

- `.github/workflows/devflow-incident.yml`
- `scripts/devflow/state_model.py`
- `scripts/devflow/validate_state.py`
- `tests/test_devflow.py`
- `docs/process/policies/notification-policy.md`
- `docs/process/runbooks/start-new-task.md`
- `docs/process/templates/task_state.template.yaml`
- `docs/implementation/ACTIVE_TASKS.yaml`
- `docs/implementation/chatgpt-web-codex-devflow-v1/task_state.yaml`
- 本计划及对应结果文档

## 禁止事项

- 不修改 F10、Raw Pack、官方验证或 Research Pack 业务逻辑；
- 不读取、记录或输出中转站 URL、Key 或模型 ID；
- 不创建第二个任务控制 Issue；
- 不让通知 Workflow 具有代码写权限；
- 不因普通 PASS 事件发送通知。

## 验收

- #31 关闭且 `state_reason=duplicate`；
- #32 保持开放并作为唯一 canonical 通道；
- `TaskState.pull_request` 可被安全解析；
- `control_issue_number` 只接受正整数或 null；
- PR 分支和 `main` 合并/合并后状态校验均通过；
- Incident Workflow 使用固定 issue number，重复事件标记不重复评论；
- Ruff、`tests/test_devflow.py`、全量 Test 和状态一致性 Gate 通过。

## 恢复入口

```yaml
stage: W05_HF02
status: RUNNING
next_action: implement_and_verify_singleton_task_control_issue
human_intervention_required: false
```
