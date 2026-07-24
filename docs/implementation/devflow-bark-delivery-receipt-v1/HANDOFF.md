# Handoff：Devflow Bark Delivery Receipt v1

## 当前检查点

- 已从 exact main `20b9a866a8d7ed8d839ef86416ac22d876167cec` 创建任务分支；
- 任务合同、总计划、W00计划、决策和canonical state已持久化；
- Codex Policy保持 `disabled`；
- 未调用Codex、Responses、Relay、历史模型Workflow或Bark；
- 未读取、显示、复制、哈希或变换 `BARK_PUSH_URL`。

## 当前阶段

```yaml
stage: W00
next_action:
  - inventory_current_incident_observability
  - define_delivery_receipt_schema
  - define_artifact_and_issue_index_contract
  - write_W00_result
  - persist_W01_plan_before_implementation
```

## 不要执行

- 不直接修改main；
- 不在实现Gate前发送Bark；
- 不创建synthetic测试Workflow；
- 不输出Endpoint、响应正文、响应头或原始curl错误；
- 不让Artifact或回执评论失败改变task state；
- 不为Bark失败触发Auto Recovery；
- 不通过UI Re-run补发；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。

## 最终真实验证

实现合并后，使用本任务自己的原子DONE closeout产生新的 `COMPLETED` generation。该逻辑事件最多执行一个Bark POST，并上传一个安全回执Artifact；随后从canonical Issue取得Incident Run ID和Artifact ID进行下载核验。