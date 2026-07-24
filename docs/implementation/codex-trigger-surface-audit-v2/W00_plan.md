# W00 计划：全仓与历史执行面审计

## 检查项

1. 当前默认分支所有 Codex、Relay、Secret 和 Auto Recovery Workflow；
2. 直接或间接模型调用引用；
3. Product Gate/Post-Merge/Auto Recovery 的 Dispatch 与重试；
4. 历史 Codex Workflow SHA；
5. 历史 Run 输入的 `task/codex-*` 分支；
6. 历史分支是否仍有 Descriptor 和可调用 Action；
7. Relay Health 是否产生付费请求及是否可自动重跑。

## Gate

```yaml
main_policy_disabled: required
current_automatic_codex_paths: 0
historical_rerun_risk_identified: true
paid_probe_risk_identified: true
codex_calls: 0
```
