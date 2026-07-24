# W03 结果：机器清单、永久Validator与操作文档

```yaml
status: PASS
verified_head_sha: 6f068f4d5b368b70faf5dfc12bc69c9f4f0aae69
upgrade_compatibility: PASS:30096468658
test: PASS:30096468735
state_consistency: PASS:30096468742
e2e_688521: PASS:30096468719
bark_requests: 0
secret_reads: 0
```

## 机器合同

notification manifest现在声明：

-独立producer路径和`workflow_run_success`触发；
- source Workflow/event/branch；
-精确source head与first-parent diff；
-single producer；
-stable completion marker；
-fail-open语义。

## 永久Validator

专用通知Validator和总Workflow Validator证明：

- scanner唯一使用者是独立producer；
- State Consistency只做验证；
- producer只接受成功main push并验证source SHA；
- producer不引用Bark Secret、Environment、Issue权限或HTTP POST；
- Incident不监听workflow_run，并在Bark前检查stable marker；
- Auto Recovery不监听producer或Incident；
- Bark POST、receipt Artifact和安全边界保持原有唯一性。

## 文档

通知Policy和Incident Runbook已更新：

-完成链路的独立Run顺序；
- task级稳定marker与generation marker的分工；
- Issue缺失时先查State Consistency和producer；
-禁止重跑旧Workflow或UI补发；
-恢复通过新任务和受审generation完成。

## 验收

四个Gate在包含代码、Validator、测试和文档的精确head全部PASS；本阶段没有Bark请求和Secret读取。