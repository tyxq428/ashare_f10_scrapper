# HANDOFF：codex-trigger-surface-audit-v2

## 当前事实

- 默认分支 Codex 入口仍为 eligibility-only，Policy 为 disabled；
- 默认分支不存在直接 `openai/codex-action` 调用；
- Product Gate、Post-Merge、State Consistency 和 Auto Recovery 不派发 Codex；
- 新发现的剩余风险是历史 Workflow Re-run 与仍存在的 `task/codex-*` 分支；
- Relay Health 会真实发送 Responses 请求，且当前被 Auto Recovery 监听；
- 本任务 Codex 调用为 0。

## 恢复入口

```text
feature/codex-trigger-surface-audit-v2
→ W01 legacy task branch quarantine
→ W02 paid probe and Secret Audit boundary
→ W03 permanent guard
```

## 下一动作

执行一次性零模型 Workflow：枚举并隔离历史任务分支，随后提交永久审计器和付费探针守卫。

## 人工门槛

无。若发现历史任务分支存在开放 PR，则停止该分支的隔离并记录具体 PR，不自动覆盖。
