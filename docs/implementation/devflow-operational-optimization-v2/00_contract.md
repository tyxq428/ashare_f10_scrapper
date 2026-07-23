# 任务合同：Devflow Operational Optimization v2

## 任务 ID

`devflow-operational-optimization-v2`

## 目标

在不改变投研业务语义、不暴露中转站 URL/Key/Model、且不降低现有无人值守安全边界的前提下，完成第二轮执行流优化：

1. 统一仓库指令与真实执行器，Codex Thin Worker 固定为 XHigh；
2. 根据改动影响选择最小充分 Gate，避免纯文档或 Devflow 变更反复运行完整 F10 E2E；
3. 只缓存依赖，不缓存 Scope、Secret Audit、Gate 或 Post-Merge 结论；
4. 为已完成任务安全回收 `task/codex-*`、`codex/*` 等临时分支；
5. 将平台执行状态与项目领域验收状态解耦，并保持旧状态文件只读兼容；
6. 用 Context Budget 控制 XHigh 的输入范围，而不是回退推理强度；
7. 增加版本升级兼容测试，保证旧 Descriptor/State 可以被新执行器安全读取或显式迁移。

## 非目标

- 不抽离独立 `devflow-kit` 仓库；
- 不修改 F10 抓取、研究口径、字段映射或官方来源优先级；
- 不扩大 Codex 自动合并范围；
- 不允许 Task Descriptor 提交任意 Shell；
- 不重新调用 Codex 验证纯执行层优化；
- 不删除尚未完成、存在开放 PR、未合并或未确认归属的分支。

## 完成定义

- 根级 `AGENTS.md`、Policies、Runbooks、Templates 与生产 Composite Action 对 XHigh 的描述一致；
- 新任务默认 `reasoning_effort=xhigh`，生产运行时拒绝静默降级；
- PR 改动被稳定分类为 `docs_only`、`devflow_only` 或 `product`，对应 Gate 可确定复现；
- 完整 E2E 仅对产品影响或显式手工请求执行；
- setup-python 使用锁定依赖文件作为 cache key，执行结论不进入缓存；
- Branch GC 只处理已验证完成任务的受管分支，支持 dry-run、开放 PR/保护分支排除和幂等；
- State schema v2 使用通用 `acceptance` 与 `security_status`，schema v1 仍可读取；
- Context Budget 在模型调用前检查允许文件数量、任务描述大小和允许文件总字节数；
- Upgrade Compatibility Gate 覆盖 schema v1→v2、历史 Low Descriptor 只读兼容和新任务 XHigh 强制；
- State Consistency、Test、影响分类测试及必要 E2E 全部通过；
- 合并后 exact-main Devflow Infrastructure Post Merge 通过；
- 形成每个工作包的计划/结果 Markdown 和最终报告。

## 暂停条件

仅在以下情况暂停：

- GitHub 权限或分支保护阻止安全提交/合并；
- 需要改变自动合并风险边界；
- Secret、安全或 Scope 审计失败；
- 现有测试证明改动会改变投研业务语义；
- 无法在既定范围内兼容历史状态或 Descriptor。
