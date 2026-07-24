# DECISIONS

## D01｜模型入口不是常驻能力

未来模型执行采用一次性 Activation PR，而不是长期保留可直接调用的 Secret-bearing Workflow。

## D02｜唯一候选入口

仅保留用户明确批准的 `manual_one_time_executor`。Product Gate、Post-Merge、Auto Recovery、State Consistency、Bot 和 GitHub Re-run 均不得创建模型调用。

## D03｜未知失败默认 Web

Codex 候选使用正向 Reason Code allowlist；未知、无法复现、业务语义、安全、Workflow、Devflow 或机械错误全部路由 ChatGPT Web / 确定性修复。

## D04｜Grant 一次性消耗

Grant 在模型 Job 启动前预占，一旦进入 `RESERVED` 或 `CONSUMED`，成功、失败、取消、超时和 Artifact 错误都不得再次启动模型。

## D05｜控制代码来自精确 Main SHA

任务分支只作为 Descriptor 与产品工作区数据源；Policy、Eligibility、Gate、Scope、Secret Audit 和 Grant 逻辑必须来自精确默认分支提交。
