# Codex Entrypoint Hardening v1 — 执行合同

## 目标

在仓库继续保持 `mode: disabled`、Codex 调用次数为 0 的前提下，清除所有潜在自动模型入口，并为未来一次性、用户明确批准的模型调用建立可信控制平面、真实零 Token 复现、必要性判断和一次性 Grant 设计。

## 不可违反的边界

- 本任务 W00–W08 全程不得调用 Codex、Relay 或 `agent-runtime`；
- 不得把 Product Gate、Post-Merge、Auto Recovery、State Consistency 或 GitHub Bot 接入模型；
- 不得以 Full Gate 失败、超时、Artifact 上传失败或 GitHub Re-run 为理由重复模型会话；
- 不得信任任务分支提供的 Policy、Eligibility 实现或自报复现结论；
- 所有未知失败默认路由 ChatGPT Web；
- 只有用户明确批准、Web 已评估不适合在当前会话完成、受信任零 Token 复现通过的局部产品代码任务，未来才可成为一次性候选；
- 优化完成后 Codex Policy 仍保持 `disabled`。

## 交付

1. 全仓模型入口清单和静态扫描；
2. 删除 Product Gate 自动 Recovery Dispatch；
3. Recovery Generation 永久有效值为 0；
4. Pre-model、Grant reservation、Model-bearing Job 和 Secret-free audit/publish 的分层设计；
5. 默认分支可信控制平面与任务分支 data-only 约束；
6. 正向 Codex Reason Code allowlist 与 Web 必要性评估；
7. 真实复现证据和一次性 Grant / Ledger 规范；
8. 一次性 Activation PR 模式；
9. 回归测试、完整 Test、真实 E2E 和 exact-main 收尾。
