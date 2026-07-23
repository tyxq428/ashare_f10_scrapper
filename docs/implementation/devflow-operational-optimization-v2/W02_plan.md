# W02 计划：影响感知 Gate 与安全缓存

## 目标

根据当前 diff 确定 `docs_only / devflow_only / product`，让稳定的 Test/E2E Check 运行最小充分门禁，只缓存依赖，不缓存任何验收或安全结论。

## 实施范围

- `scripts/devflow/change_impact.py` 与 Fixture；
- `.github/workflows/test.yml`；
- `.github/workflows/e2e-688521.yml`；
- `.github/workflows/devflow-infrastructure-post-merge.yml`；
- setup-python pip cache，依赖键为 `pyproject.toml`；
- Workflow 静态检查和 Policy。

## 验收

- 未知路径和混合改动保守升级为 `product`；
- docs/devflow PR 不执行真实 F10 抓取但 E2E Check 为明确 PASS；
- 手工派发可强制完整 Test/E2E；
- Scope、Secret、Gate、Diff、main 和 Post-Merge 结论永不缓存。
