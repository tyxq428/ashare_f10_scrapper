# W01-HF01 计划：阻止无效 State Consistency Codex 循环

## 背景

以下 Codex Task Run 在模型调用后均返回 `BLOCKED`，没有修改文件，但恢复控制器继续把失败作为可再次派发/重跑的 Codex 修复：

- `30017775182`
- `30017841410`
- `30020008656`
- `30020054688`

真实失败来自活动功能分支中的新 Devflow 文件、测试或格式问题，而自动恢复器却从 `main` 合成一个固定五文件 State Consistency 描述符。该描述符既不携带不可变失败上下文，也不允许修改真实失败路径，因此 Codex 无法安全修复，只能消耗 XHigh 额度后返回 `BLOCKED`。

## 目标

1. 在根因修复完成前全局熔断 Codex 模型调用；
2. 删除 State Consistency 缺少原始 Task Descriptor 时的合成 Codex Descriptor；
3. `codex-result.json.status=BLOCKED` 时禁止 `RETRY_CODEX` 和新 Recovery Generation；
4. 只有存在不可变任务描述符、真实失败证据且允许范围覆盖失败路径时，才允许 Codex Repair；
5. Devflow/Workflow/状态模型类改动优先由 ChatGPT Web Supervisor 直接修复；
6. 增加回归测试和静态 Workflow 约束；
7. Gate 通过后恢复 Codex，但保留可操作的全局熔断机制。

## 允许修改

- `.github/workflows/devflow-auto-recovery.yml`
- `.github/actions/codex-thin-worker/action.yml`
- `scripts/devflow/recovery_policy.py`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- `tests/test_devflow_codex_environment.py`
- `docs/process/policies/security-and-codex.md`
- `docs/process/runbooks/automatic-recovery.md`
- `docs/ENGINEERING_ISSUES_AND_LESSONS.md`
- 本工作包计划与结果文档

## 验收

- 结构化 `BLOCKED` 结果永不触发模型重试；
- State Consistency 无不可变任务上下文时不生成 Codex 分支；
- 熔断开启时任何任务分支都不能调用模型；
- Devflow 定向测试、Workflow 静态校验、Ruff、完整 Test 通过；
- 不新增 Codex 调用；
- 不泄露 Endpoint、Key 或 Model。
