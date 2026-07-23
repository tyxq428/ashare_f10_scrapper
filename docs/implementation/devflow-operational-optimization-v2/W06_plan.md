# W06 计划：PR、合并后验证与收尾

## 目标

在隔离分支完成静态与运行门禁，合并后按 exact-main 影响分类复验，并以版本化结果文档关闭任务。

## 合并前 Gate

- Devflow State Consistency（全部索引任务）；
- Test（本次应分类为 `devflow_only`）；
- E2E 688521（本次应稳定 PASS 且不抓取真实数据）；
- Devflow Upgrade Compatibility；
- Workflow 静态安全与 Action SHA；
- Ruff / `tests/test_devflow*.py`；
- 手工强制完整 Test 和真实 E2E 各一次，验证强制路径仍可用。

## 合并后 Gate

- `Devflow Infrastructure Post Merge` 在 exact `main` 上 PASS；
- State/Template/Docs/Upgrade 全部 PASS；
- 无 Secret、URL、模型 ID 或 Prompt 泄漏；
- 无临时 Workflow；
- Branch GC 保持 dry-run；
- 生成 W01–W06 结果、FINAL_REPORT，并把任务状态迁移为 schema-v2 DONE。
