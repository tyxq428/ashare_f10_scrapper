# W05-HF02 计划：任务控制 Issue 单例化与状态模型修复

## 背景

多个 `workflow_run` 事件几乎同时结束时，旧通知逻辑会由不同运行独立查询和创建同名任务控制 Issue，最终产生 #31 与 #32 两个通道。与此同时，第一版 merge-state 修复引用了尚未在 `TaskState` 中建模的 `pull_request` 字段。

## 目标

1. 将 #32 固定为任务 `chatgpt-web-codex-devflow-v1` 的唯一 canonical 控制 Issue；
2. 将 #31 按 duplicate 关闭；
3. 在 canonical state 中持久化 `notification.control_issue_number`；
4. 合并两个 Incident Workflow 的职责，所有通知来源进入同一串行队列；
5. 使用 workflow run + notification type 的稳定标记去重评论；
6. 在 `TaskState` 中解析并校验 `pull_request` 和 `control_issue_number`；
7. 保留“普通阶段、PASS、审计通过不通知”的策略。

## 修改范围

- `.github/workflows/devflow-incident.yml`
- 删除 `.github/workflows/devflow-infrastructure-incident.yml`
- `scripts/devflow/state_model.py`
- `scripts/devflow/validate_state.py`
- `tests/test_devflow.py`
- `docs/process/policies/notification-policy.md`
- `docs/process/runbooks/start-new-task.md`
- `docs/process/templates/task_state.template.yaml`
- `docs/implementation/chatgpt-web-codex-devflow-v1/task_state.yaml`
- 本计划及结果文档

## 安全约束

- 不修改 F10、Raw Pack、官方验证或 Research Pack 业务逻辑；
- 不读取、记录或输出中转站 URL、Key 或模型 ID；
- Incident Workflow 保持 `contents: read`、`issues: write`；
- 不为普通成功状态创建 Issue 或评论；
- 不在本 Hotfix 中调用 Codex。

## 验收 Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
python scripts/devflow/validate_state.py
现有完整 Test Workflow
Devflow State Consistency
```

## 恢复入口

```yaml
stage: W05_HF02
status: RUNNING
next_action: rebase_hotfix_pr_and_run_all_gates
human_intervention_required: false
```
