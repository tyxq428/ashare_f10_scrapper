# 决策记录

## D001｜旧 lockdown-v2 不直接实施

该分支相对当前 main 仅新增 7 个任务文档，没有 Workflow、脚本、Action 或产品代码变更，也没有开放 PR。其大部分目标已由 PR #52 以更安全的方式完成。

## D002｜保留 eligibility-only `codex-task.yml`

当前 Workflow 只有人工 `workflow_dispatch`、只读权限、精确 main 控制面与 data-only 任务分支检查；不绑定 Environment、不读取 Secret、不启动 Forwarder，也不包含模型 Action。保留它比删除后依赖临时、非标准化候选检查更容易审计。未来真正模型调用仍必须通过独立受审的一次性 Activation PR。

## D003｜Workflow 平台 active/disabled 状态不是模型安全前提

即使当前 `Codex Task` Workflow 在 GitHub 平台处于 active，其源码也只能执行零 Token 候选检查。历史模型 Run 的重放风险已由 PR #52 对 88 个历史 `task/codex-*` 分支的隔离处理。平台状态仍应记录，但不作为未闭合模型触发面。

## D004｜Relay Health 的付费模式是受控诊断面，不是自动触发面

它只能人工派发，默认 `configuration_only`，付费模式需要精确确认、用途说明且仅允许首次 run attempt。Auto Recovery 不监听 Relay Health。因此保留该受控诊断面，不执行探针。

## D005｜Environment 保护必须由平台元数据证明

当前连接器不能读取或修改 Required Reviewer、管理员绕过与 Deployment Branch Policy。不得用仓库文档替代平台保护证据；该项进入真实 `WAITING_HUMAN`。
