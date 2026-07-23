# W05-HF08 Plan：将后续 Codex Thin Worker 固定为 XHigh

## 背景

用户明确要求：后续只要发生真实 Codex 模型调用，统一使用 `xhigh` 推理强度，不再使用 `low`。当前正式 Action 仍硬编码 `effort: low`，任务模板和自动恢复生成器也写入 `reasoning_effort: low`。

## 目标

1. 将正式 `openai/codex-action` 调用固定为 `effort: xhigh`；
2. 将新任务模板与自动恢复任务默认值改为 `xhigh`；
3. 保留对历史 `low` 描述符的只读兼容，避免已经发布的 v3 候选在 Product Gate/Post-Merge 阶段因元数据升级而失效；
4. 更新静态 Workflow 校验、回归测试、政策和 Runbook；
5. 不重新调用 Codex，不重新消耗模型额度；现有 v3 产品候选继续复用。

## 允许修改

- `.github/actions/codex-thin-worker/action.yml`
- `.github/workflows/devflow-auto-recovery.yml`
- `scripts/devflow/task_descriptor.py`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- `tests/test_devflow_codex_environment.py`
- `docs/process/templates/codex_task.template.yaml`
- `docs/process/policies/security-and-codex.md`
- `docs/process/runbooks/run-codex-thin-worker.md`
- 当前任务状态与经验文档

## 兼容策略

- 运行时唯一有效强度：`xhigh`；
- 新 Task Descriptor 默认：`xhigh`；
- Parser 暂时接受 `low` 与 `xhigh`，只用于读取历史控制分支；
- Recovery Generation 由新生成器写入 `xhigh`；
- 不从历史 Descriptor 动态降级 Action 的运行强度。

## Gate

- `python scripts/devflow/validate_workflows.py`
- `ruff check scripts/devflow tests/test_devflow.py tests/test_devflow_codex_environment.py`
- `pytest -q tests/test_devflow.py tests/test_devflow_codex_environment.py`
- 完整 `Test`
- `E2E 688521`
- `Devflow State Consistency`

## 停止条件

- 当前模型端点明确不支持 `xhigh`；
- 静态校验或测试显示历史 Descriptor 无法继续 Product Gate/Post-Merge；
- 修改需要暴露或改变任何 Secret。
