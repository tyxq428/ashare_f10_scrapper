# W03 计划：机器清单、永久Validator与操作文档

## 目标

把独立producer和stable completion marker固化为长期机器合同，防止后续重新嵌入State Consistency、创建第二producer或扩大通知触发面。

## Manifest

`completion_producer` 必须声明：

- workflow：`devflow-terminal-state-notify.yml`；
- trigger：`workflow_run_success`；
- source Workflow：State Consistency；
- source event：push；
- source branch：main；
-精确source head checkout；
- first-parent diff；
- single producer；
- failure不改变task state。

canonical Issue必须声明stable completion marker。

## Validator

证明：

-只有producer使用scanner；
-State Consistency没有scanner/dispatch/contents write；
-producer筛选成功main push并验证source SHA；
-producer零Secret、零Environment、零Bark、零Issue写权限；
-Incident只有repository_dispatch入口并使用stable marker；
-Auto Recovery不监听producer或Incident；
-Bark/receipt边界保持不变。

## 文档

更新通知Policy与Incident Runbook：

-独立producer观察顺序；
-稳定marker语义；
-完成Issue缺失时如何诊断；
-禁止重跑旧Workflow；
-恢复必须使用受审新任务而非盲目补发。

## Gate

```yaml
manifest_validator: PASS_required
workflow_validator: PASS_required
docs_validator: PASS_required
pytest: PASS_required
bark_requests: 0
```