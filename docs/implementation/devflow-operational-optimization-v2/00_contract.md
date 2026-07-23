# 任务合同：Devflow Operational Optimization v2

## 目标

在不调用任何 Codex Thin Worker、不访问 Relay Secrets、不改变 F10 业务语义的前提下，完成执行流的运行优化和 Codex 最小使用治理。

## 强制边界

- 本任务全部由 ChatGPT Web Supervisor 和确定性 GitHub Actions 完成；
- 优化期间 Codex 调用次数必须为 0；
- 完成后 `.devflow/codex-policy.yaml` 仍保持 `mode: disabled`；
- Bot、Auto Recovery、State Consistency、Post-Merge 和 failed-job rerun 均不得启动模型；
- 将来只有用户针对不可变任务显式授权，并通过失败复现、失败文件覆盖、Context Budget、重复指纹和用量预算检查后，才可成为候选；
- 本任务不更改 F10 数据源、字段口径、研究语义或产品功能。

## 完成标准

1. W00–W07 的计划与结果文档齐全；
2. 十次历史浪费调用均被回归测试判定为不具备 Codex 资格；
3. State Consistency、Upgrade Compatibility、Workflow 静态安全、Ruff 和 Devflow 测试全部通过；
4. 手工强制的完整 Test 和真实 E2E 通过；
5. 合并后 exact-main 基础设施回归通过；
6. Canonical State 为 `DONE / COMPLETED / PASS`；
7. Codex 默认禁用状态保持不变。
