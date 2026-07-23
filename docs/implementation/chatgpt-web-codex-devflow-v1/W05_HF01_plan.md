# W05_HF01 计划：修复 main 上的状态一致性误报

## 现象

`DevFlow State Consistency` 在 `main` 上运行时失败，并触发 `[TASK][INTERRUPTED]` 通知。

## 根因

Canonical state 仍记录功能工作分支，这是正确的；但状态校验器把 `main` 上的合并后验证误判为工作分支不一致。该检查只适用于合并前工作分支，不应阻止 W05 及之后的默认分支验证。

## 修改范围

- `scripts/devflow/validate_state.py`
- `tests/test_devflow.py`

## 目标

1. 合并前仍严格要求 checkout 与 `working_branch` 一致；
2. 已有关联 PR 且进入 W05 或之后时，允许在 `main` 运行合并/合并后门禁；
3. 其他不相关分支仍必须失败；
4. 不修改业务代码、Secrets、Codex Workflow 或通知策略。

## 验收

```bash
ruff check scripts/devflow/validate_state.py tests/test_devflow.py
pytest -q tests/test_devflow.py
python scripts/devflow/validate_state.py
```

## 恢复入口

```yaml
phase: W05_HF01
checkpoint: HOTFIX_IMPLEMENTED
next_action: open_hotfix_pr_and_run_gates
```
