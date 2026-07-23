# W02 计划：Canonical State、状态渲染与一致性引擎

## 目标

建立不依赖聊天历史和第三方 YAML 依赖的确定性状态模型，自动校验活动任务、阶段文档、人工门槛、post-merge 完成条件、产品提交祖先关系，并从 canonical state 生成 `STATUS.md` 与 `HANDOFF.md`。

## 实施文件

- `scripts/devflow/state_model.py`
- `scripts/devflow/validate_state.py`
- `scripts/devflow/render_task_docs.py`
- `tests/test_devflow.py`

## 关键规则

1. `.yaml` 使用 JSON-compatible YAML，由 Python 标准库 `json` 解析；
2. 同一 task ID 在 `ACTIVE_TASKS.yaml` 中只能出现一次；
3. 活动任务必须有 contract、master plan、state、handoff 和当前 stage plan；
4. `Wxx_result.md` 不得在对应 plan 缺失时存在；
5. `DONE` 必须满足 execution success、acceptance 非 pending、post-merge PASS、human gate false；
6. `WAITING_HUMAN` 必须提供 reason、minimum_action 和 recovery entry；
7. `last_product_commit_sha` 必须是当前 HEAD 的祖先，但允许其后存在纯状态/文档提交；
8. 渲染输出必须可重复，相同 state 不产生不同结果。

## Thin slice

使用临时目录构造一个合法任务和四个非法任务：重复活动任务、结果缺少计划、DONE 无 post-merge、人工门槛缺少最小动作。

## Gate

```text
python -m compileall -q scripts/devflow
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
```

## 恢复入口

```yaml
phase: W02
checkpoint: W02_PLAN_COMMITTED
next_action: implement_and_test_state_engine
human_intervention_required: false
```
