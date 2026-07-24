# Handoff：Devflow Terminal Notification Recovery v1

## 最终检查点

- W00–W05均已完成并有计划/结果记录；
- PR #58已以 `1f20a6531329ce957d9a3d5a0478071b92d11496` 合入main；
- 精确实现head `aaa63aa9b89dd4eda9b3b6e70ea59f90937a2dcf` 的Upgrade Compatibility、Test、State Consistency和真实688521 E2E全部PASS；
- merge commit相对该已验证head无文件差异；
- State Consistency仅负责验证，独立producer负责成功后续通知；
- Incident stable completion marker阻止同一任务跨generation重复完成Bark；
- closeout PR #59原子发布DONE state和notification generation 1；
- Codex Policy保持disabled；
- closeout前未调用Codex、Responses、Relay、历史模型Workflow或Bark；
- 未读取、显示、复制、哈希或变换 `BARK_PUSH_URL`。

## 最终状态

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
stage: W05
last_completed_stage: W05
branch: main
pull_request: 58
implementation_merge_sha: 1f20a6531329ce957d9a3d5a0478071b92d11496
closeout_pull_request: 59
next_action: none
human_intervention_required: false
```

## 自动观察链

PR #59合入main后：

```text
Devflow State Consistency PASS on exact main
→ Devflow Terminal State Notification
→ devflow_notify
→ canonical Issue COMPLETED marker
→ stable devflow-task-completed:<task-id> marker
→ at most one Bark POST
→ bark-delivery-result.json
→ single-file Artifact
→ [BARK][DELIVERY_RECEIPT] Issue index
```

producer、dispatch、Bark、回执生成、Artifact上传或Issue索引失败均为fail-open，不决定canonical DONE。

## 后续观察规则

1. 找到 `[TASK CONTROL] devflow-terminal-notification-recovery-v1`；
2. 确认COMPLETED marker和stable completion marker各出现一次；
3. 记录State Consistency、独立producer和Incident Run ID；
4. 从回执索引读取Artifact ID；
5. 下载ZIP并确认只包含一个 `bark-delivery-result.json`；
6. 运行 `python scripts/devflow/bark_delivery_result.py validate --input bark-delivery-result.json`；
7. 记录 `delivery_status`、`request_initiated`、`request_attempts`、`curl_exit_code` 和 `http_status`；
8. 仅用纯文档观察PR追加实际结果，不修改task state、ACTIVE_TASKS或notification generation。

## 长期禁止

- 不重跑旧State Consistency、producer或Incident；
- 不通过GitHub UI Re-run补发Bark；
- 不创建任意payload synthetic测试；
- 不输出Bark Endpoint、响应正文、响应头、raw error或Secret；
- 不让通知观察层失败改变任务结果；
- 不为Bark失败触发Auto Recovery；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。
