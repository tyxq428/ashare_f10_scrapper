# 决策记录

## D001｜源码禁用与平台禁用分开验收

`main` 中没有模型代码，只能证明新 Run 不会从当前定义调用模型；不能自动证明历史 Run 的重跑按钮、旧分支 Workflow 或 Environment Secrets 已失效。因此此次任务增加 Workflow 状态、历史分支和 Environment 三类平台证据。

## D002｜原计划不再删除 eligibility-only Workflow

原计划认为常驻 eligibility-only Workflow 会留下误解空间。PR #52 后的最终实现证明，保留一个只读、零 Secret、零模型、精确 main 控制面和 data-only 工作区的标准候选检查入口，更易于持续静态审计。真正模型执行仍必须由一次性受审 Activation PR 创建。

## D003｜旧分支隔离优于批量删除

PR #52 对 88 个历史 `task/codex-*` 分支移除 Descriptor、安装禁用 Action并持续审计，既关闭历史 rerun 模型面，又保留审计证据，优于不可逆批量删除。

## D004｜Environment 不能靠仓库文档替代审批

如果 `agent-runtime` 仍允许无审批部署，平台防御纵深仍需核验。当前连接器无法读取或修改该元数据，剩余检查转入 reconciliation-v3。

## D005｜本任务终止为已被替代

本分支没有实现代码和开放 PR。仓库层目标由 `codex-trigger-surface-audit-v2` / PR #52 完成；平台元数据差异由 `codex-trigger-surface-reconciliation-v3` / PR #53 接管。本任务不再继续 W01–W08。
