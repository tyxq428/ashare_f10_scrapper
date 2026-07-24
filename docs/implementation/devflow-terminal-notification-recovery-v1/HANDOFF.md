# Handoff：Devflow Terminal Notification Recovery v1

## 当前检查点

- 已从closeout main `5afbb17a574bb850e93d6134719b621e3fdfd10c` 创建新任务分支；
- 上一Bark receipt任务canonical state为DONE，但没有对应task-control Issue；
- 任务合同、总计划、W00计划和决策已持久化；
- Codex Policy保持disabled；
- 未调用Codex、Responses、Relay、历史模型Workflow或Bark；
- 未读取或显示Bark Secret。

## 当前阶段

```yaml
stage: W00
next_action:
  - record_missing_completion_issue_evidence
  - add_independent_workflow_run_success_producer
  - remove_embedded_state_consistency_producer
  - add_stable_completion_marker
  - write_W00_result_and_W01_plan
```

## 不要执行

- 不修改已完成旧任务的notification generation；
- 不重跑旧State Consistency或Incident；
- 不通过UI Re-run补发；
- 不创建任意payload synthetic测试；
- 不读取或输出 `BARK_PUSH_URL`；
- 不让producer失败改变canonical任务结果；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。

## 最终验证

修复合并后，以本任务自己的原子DONE closeout触发独立producer。只有一个stable completion marker可进入Incident，随后最多一个Bark POST和一个安全回执Artifact。