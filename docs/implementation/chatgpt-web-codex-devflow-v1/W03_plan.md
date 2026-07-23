# W03 计划：Gate Profiles、Scope Guard 与 Failure Bundle

## 目标

把可确定性执行的约束从自然语言转为脚本：任务只选择受信任 Gate Profile，不传任意 Shell；Codex 和 Publish 两侧都校验修改范围；失败时生成有界、可恢复且不泄露 Secret 的 Failure Bundle。

## 实施文件

- `scripts/devflow/verify_changed_paths.py`
- `scripts/devflow/run_gate_profile.py`
- `scripts/devflow/build_failure_bundle.py`
- 扩展 `tests/test_devflow.py`

## Gate Profiles

第一版只提供：

- `devflow-targeted`：devflow 脚本编译、Ruff、`tests/test_devflow.py`；
- `resilient-command-targeted`：重试脚本和对应测试；
- `state-consistency`：canonical state 和生成文档检查。

未知 Profile 必须 fail closed。任务输入不得拼接到 Shell。

## Scope Guard

- 支持以基线 SHA 对比已跟踪修改；
- 同时检查 staged、unstaged 和 untracked；
- 允许显式文件和目录前缀；
- 发现一个越界路径即返回 `SECURITY_BLOCKED`；
- 不输出文件内容。

## Failure Bundle

- 只保留有界日志尾；
- 记录失败分类、命令、exit code、尝试次数、changed files、已保留检查点、最小人工动作和恢复入口；
- 对 Secret 模式只记录布尔结果，不写命中值。

## Gate

```text
python -m compileall -q scripts/devflow
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
```

## 恢复入口

```yaml
phase: W03
checkpoint: W03_PLAN_COMMITTED
next_action: implement_scope_gate_and_failure_bundle
human_intervention_required: false
```
