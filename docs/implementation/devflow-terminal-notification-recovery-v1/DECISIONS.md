# 决策记录

## D001｜将完成Producer从State Consistency本体分离

验证Workflow和通知生产属于不同职责。独立 `workflow_run` success producer提供单独Run、Job和日志，且只有State Consistency成功后才运行。

## D002｜Incident继续只监听repository_dispatch

`Devflow Incident` 不直接监听raw `workflow_run`。独立producer先验证source Workflow、event、branch、conclusion和精确head，再发送既有 `devflow_notify` 合同。

## D003｜每个Task使用稳定完成Marker

Generation marker保留审计精度；额外使用 `devflow-task-completed:<task-id>` 作为跨generation稳定去重键。恢复generation、Workflow重跑或迟到事件不能产生第二次Bark。

## D004｜Producer失败仍Fail Open

完成通知是辅助通道。producer扫描或dispatch失败不得让已经通过的State Consistency和canonical DONE变成失败，也不得进入Auto Recovery。

## D005｜不用旧Task重发

不修改已完成 `devflow-bark-delivery-receipt-v1` 的generation。可靠性修复由新任务交付，并使用新任务自己的完成事件做一次真实验证。

## D006｜不使用Gmail或Synthetic测试

验证来源限定为GitHub State Consistency、Terminal Producer、canonical Issue、Incident Run和安全回执Artifact。不会搜索邮件，也不会创建任意payload测试按钮。