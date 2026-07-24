# 决策记录

## D01：当前 main 禁用不等于历史 Run 不可重跑

GitHub Actions 历史 Re-run 使用原 Workflow 定义。若原 Workflow 读取一个仍存在的 `task/codex-*` 分支，则只修改当前 `main` 不足以证明历史模型调用已失效。

决策：所有历史任务分支必须单独隔离，并由永久审计持续验证。

## D02：历史分支使用 fast-forward 隔离，不改写历史提交

不强制删除历史提交或强推覆盖。对无开放 PR 的历史任务分支追加隔离提交：删除任务描述、安装禁用 Action、写隔离标记。

## D03：Relay Health 属于付费探针

它不是 Codex Thin Worker，但会真实调用 Responses API。默认运行模式必须为零请求配置检查；付费探针只能由仓库所有者明确确认，且任何失败都不得自动重跑。

## D04：Secret Audit 只审计明确的模型 Run

Secret Audit 不应由普通 `Codex Task` 或零 Token Candidate Review 自动触发。它需要精确 Run ID、Activation ID 和模型已启动证据，并在这些零 Secret 检查通过后才能绑定 Environment。

## D05：本轮不恢复模型执行器

本轮只加固触发面和历史执行面。`codex-task.yml` 继续是 eligibility-only；未来模型执行仍需独立 Activation PR 和用户再次授权。
