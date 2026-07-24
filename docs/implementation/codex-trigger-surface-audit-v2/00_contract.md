# 执行合同：Codex Trigger Surface Audit v2

## 目标

在仓库保持 `mode: disabled`、优化过程 Codex 调用为 0 的前提下，继续审计所有可能产生模型调用或重复付费探针的执行面，并修复默认分支静态扫描无法覆盖的历史 Workflow Re-run 风险。

## 已确认的新增风险

1. 历史 `Codex Task` Workflow Re-run 使用原 Workflow 定义，并重新读取当时的 `task/codex-*` 分支；当前 `main` 的禁用入口不能单独覆盖这种历史执行。
2. 部分历史任务分支仍存在 `.agent/current_task.yaml`，因此必须显式隔离或封存，不能只依赖默认分支 Policy。
3. `Devflow Relay Health` 会真实调用 Responses API；即使不是 Codex Thin Worker，也属于可能产生额度消耗的付费探针。
4. `Devflow Relay Health` 仍处于 Auto Recovery 监听范围，整体超时或基础设施分类可能造成自动重跑付费探针。
5. `Devflow Secret Audit` 虽不调用模型，但仍会读取 `agent-runtime`，需要证明它只接受人工指定的真实模型 Run，不能被零 Token 候选检查自动带起。

## 硬约束

```yaml
codex_policy: disabled
codex_calls_during_task: 0
automatic_model_paths: 0
historical_codex_rerun_model_paths: 0
relay_paid_probe_auto_retry: false
secret_audit_automatic_trigger: false
```

- 不调用 Codex Thin Worker；
- 不调用 Responses API 作为本任务验证手段；
- 不读取或输出 Relay URL、Key、Model；
- 不删除历史提交；对历史任务分支使用可审计的 fast-forward 隔离提交；
- 不影响 F10 业务语义；
- 所有修改由 ChatGPT Web 和确定性 GitHub Actions 完成。

## 完成定义

- 仓库中所有仍存在的 `task/codex-*` 历史分支均通过 rerun quarantine 审计；
- 历史分支无法进入 Secret-bearing Codex Job；
- 默认分支 CI 能持续发现新增的未隔离历史任务分支；
- Relay Health 只有带显式付费确认的人工执行路径，且不被 Auto Recovery 重跑；
- Secret Audit 不再由普通 `Codex Task` 完成事件自动触发；
- State、Workflow、Upgrade、完整 Test、真实 E2E 和 exact-main 全部通过；
- 最终状态为 `DONE`，Codex Policy 仍为 `disabled`。
