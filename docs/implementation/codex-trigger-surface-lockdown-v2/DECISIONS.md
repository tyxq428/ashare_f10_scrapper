# 决策记录

## D001｜源码禁用与平台禁用分开验收

`main` 中没有模型代码，只能证明新 Run 不会从当前定义调用模型；不能自动证明历史 Run 的重跑按钮、旧分支 Workflow 或 Environment Secrets 已失效。因此此次任务增加 Workflow 状态、历史分支和 Environment 三类平台证据。

## D002｜未来不保留常驻 Codex Workflow

常驻 eligibility-only Workflow 仍会留下手工按钮、历史 Workflow ID 和误解空间。未来若需要模型，必须由任务级 Activation PR 临时创建执行器，执行一次后删除并重新禁用。

## D003｜旧分支只做可证明安全的清理

只有同时满足“已并入 main、没有开放 PR、属于受管前缀”的分支才自动删除；其他分支生成报告，不强推、不覆盖。

## D004｜Environment 不能靠仓库文档替代审批

如果 `agent-runtime` 仍允许无审批部署，旧 Workflow 历史重跑仍可能在代码之外接触 Secrets。优先设置 GitHub Environment Required Reviewer；平台 API 不允许自动修改时，任务不得声称此风险已完全关闭。
