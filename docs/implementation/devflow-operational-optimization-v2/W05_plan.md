# W05 计划：版本升级兼容

## 目标

用不可变 Fixture 和独立 Workflow 验证 State、Task Descriptor 和 XHigh 执行策略升级，防止历史任务被重新打开或运行时静默降级。

## 实施范围

- `scripts/devflow/upgrade_compatibility.py`；
- `tests/fixtures/devflow/**`；
- `tests/test_devflow_upgrade_compatibility.py`；
- `.github/workflows/devflow-upgrade-compatibility.yml`；
- 静态 Workflow Policy 与 Runbook。

## 验收

- v1/v2 State 均可读；
- v1 Low Descriptor 只读兼容但 effective effort 为 XHigh；
- v2 必须 XHigh + 显式 Context Budget；
- v2 Low、未知 State/Descriptor schema 均拒绝；
- v1→v2 State 预览非破坏、幂等并保持 DONE。
