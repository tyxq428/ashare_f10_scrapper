# 决策记录：devflow-operational-optimization-v2

## D01｜XHigh 是运行时强制策略

- **决定**：生产 Composite Action 固定 `effort: xhigh`；根/Scoped `AGENTS.md`、模板和 Runbook 同步描述。
- **理由**：执行器是最终事实来源，文档不得保留 `low effort` 漂移。
- **兼容**：历史 schema-v1 Descriptor 的 `low` 仅用于只读兼容，不能降低真实调用强度。

## D02｜成本控制依赖 Context Budget，不依赖降低推理强度

- **决定**：通过允许文件、字节数、日志摘要、一次 Session 和一次 Recovery Generation控制成本。
- **禁止**：静默从 XHigh 降为 High/Low；向模型传完整聊天历史或完整 SOP。

## D03｜影响分类采用保守升级

- **决定**：未知路径、混合业务/Devflow 改动一律升级到 `product`；只有明确安全的文档集合才能判定 `docs_only`。
- **理由**：宁可多跑 Gate，也不能因误判漏测。

## D04｜缓存只用于依赖

- **允许**：pip/npm 下载缓存和稳定工具缓存。
- **禁止**：Scope、Secret Audit、Diff、Gate、Post-Merge、当前 main、Artifact 完整性结论。

## D05｜Branch GC 首先 dry-run

- **决定**：第一版默认 dry-run；只有精确完成事件携带的 task/publish 分支在通过祖先、开放 PR、活动任务与前缀检查后才可删除。

## D06｜State schema v2 保持 v1 只读兼容

- **决定**：新任务使用通用 Acceptance 和 Security Status；旧 `research_acceptance_status` 被映射但不要求重写历史证据。

## D07｜本任务不使用 Codex 修改 Workflow

- **决定**：本任务修改 `.github/**`、状态模型和安全策略，属于高风险执行基础设施，由 ChatGPT Web Supervisor 直接实施、审查和合并。
