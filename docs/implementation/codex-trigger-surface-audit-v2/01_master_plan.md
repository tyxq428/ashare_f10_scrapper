# 总体计划：Codex Trigger Surface Audit v2

## 执行流

```text
W00 全仓与历史执行面审计
→ W01 历史 Codex Workflow Re-run 分支隔离
→ W02 付费 Relay 探针与 Secret Audit 触发边界
→ W03 永久静态扫描和新分支守卫
→ W04 合并前零模型完整验证
→ W05 exact-main 收尾与最终报告
```

## W00：全仓与历史执行面审计

- 复核默认分支 `codex-task.yml`、Product Gate、Post-Merge、Auto Recovery；
- 搜索直接 `openai/codex-action`、Codex Workflow dispatch、Recovery Generation 和模型 Secret；
- 检查历史 Codex Run 使用的 Workflow SHA 和任务分支；
- 建立风险清单和不可变证据。

## W01：历史 Re-run 隔离

- 枚举远端 `task/codex-*` 分支；
- 检查是否存在开放 PR；
- 对已关闭任务分支执行 fast-forward quarantine：
  - 移除 `.agent/current_task.yaml`；
  - 覆盖为默认分支的禁用 Composite Action；
  - 写入机器可读隔离标记；
- 生成逐分支审计报告；
- 增加永久只读审计 Workflow，发现未隔离分支时 Fail Closed。

## W02：付费探针边界

- 将 Relay Health 改为默认配置检查，不发送模型请求；
- 真实 Responses 探针必须人工提供精确确认短语与目的；
- 从 Auto Recovery 监听列表移除 Relay Health，禁止任何自动重跑；
- Secret Audit 保持人工显式输入，并在读取 Environment 前验证来源 Run 与 Activation 标识。

## W03：静态和运行时守卫

- 扩展 `.devflow/codex-entrypoints.yaml`；
- 扩展 `validate_codex_entrypoints.py`，覆盖：
  - 历史任务分支；
  - 付费探针；
  - Secret Audit；
  - 所有直接和间接模型入口；
- 新增回归 Fixture，证明历史 Re-run、重复 Dispatch、Relay 超时和普通 Secret Audit 都不会启动模型。

## W04：合并前验证

- Codex 调用 0；
- State Consistency；
- Upgrade Compatibility；
- Devflow 单元与静态检查；
- 完整产品 Test；
- 真实 688521 E2E；
- 历史分支审计为 PASS。

## W05：合并与 exact-main

- 合并正式 PR；
- 在精确 `main` 上重复入口扫描、完整 Test 和真实 E2E；
- 写入 W01–W05 结果和 `FINAL_REPORT.md`；
- 更新 `task_state.yaml`、`STATUS.md`、`HANDOFF.md`、`ACTIVE_TASKS.yaml`；
- 删除一次性执行器；
- 保持 `mode: disabled`。

## 预计模型用量

```yaml
codex_sessions: 0
responses_paid_health_checks: 0
relay_secrets_read_by_implementation: false
```
