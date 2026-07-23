# 总计划：Devflow Operational Optimization v2

## 执行路径

```text
W00 Codex 全局冻结
→ W01 从冻结后的 main 建立干净分支并同步熔断修复
→ W02 确定性修复 State、格式、路径和兼容性问题
→ W03 XHigh Context Budget、影响感知 Gate 和依赖缓存
→ W04 执行状态/领域验收/安全状态解耦与 Branch GC dry-run
→ W05 升级兼容和 Codex 最小资格门禁
→ W06 零模型预合并门禁、完整 Test 和真实 E2E
→ W07 合并、exact-main 验证和 Canonical Closeout
```

## 核心策略

- 默认路由始终是 ChatGPT Web；
- Auto Recovery 只重试已验证的基础设施故障；
- State、Workflow、Devflow Core、格式、Fixture、权限、安全和业务语义问题禁止调用 Codex；
- Codex Task Workflow 在默认禁用状态下没有模型 Job，也不读取 Environment Secrets；
- 影响感知 Gate 只减少日常无意义执行，不替代合并前的一次完整产品回归；
- Branch GC 默认只生成计划，不删除远端分支；
- Schema v1 只读兼容，Schema v2 为当前写入格式；
- 全部阶段 Codex 预算为 0。

## 回滚

任何新机制失败时，保持 `mode: disabled`，回滚至最新通过的 main，并由 ChatGPT Web 根据确定性日志修复；不得通过扩大 Codex 范围或重跑模型来掩盖问题。
