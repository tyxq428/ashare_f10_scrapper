# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00–W03已完成并有计划/结果文档；
- Incident已泛化到任意登记任务，canonical Issue marker去重和单次Bark Transport已实现；
- canonical完成事件只在State Consistency全部Gate PASS后产生；
- 通知扫描、dispatch和Bark发送失败均为fail-open，不改变canonical任务结果，也不触发Auto Recovery；
- 失败类终态由Auto Recovery集中分类，Product Gate和Post Merge不再重复通知；
- 通知机器清单、永久Validator、策略和Runbook已完成；
- 精确head `ac84df7f8337ee223a5958619462007c41dbad38` 的四个确定性Gate全部PASS；
- Draft PR #54保持开放；
- Codex Policy保持 `disabled`；
- 未调用Codex、Responses、Relay或Bark；
- 未读取或配置任何Secret。

## 当前阶段

```yaml
stage: W04
last_completed_stage: W03
pull_request: 54
next_action:
  - wait_for_final_exact_PR_head_checks
  - inspect_only_failed_deterministic_checks
  - fix_without_model_paid_probe_or_live_bark
  - write_W04_result
  - persist_W05_platform_configuration_plan
  - enter_real_WAITING_HUMAN_gate
```

## 不要执行

- 不监听所有 `workflow_run: completed`并直接通知；
- 不把 `BARK_PUSH_URL`写入仓库、Issue、PR、Artifact、聊天或日志；
- 不复用 `agent-runtime`；
- 不为通知失败触发Auto Recovery；
- 不自动重试Bark；
- 不在平台配置完成前发送真实Bark；
- 不在平台配置完成前合并PR #54；
- 不调用或测试Codex、Responses、Relay或历史模型Workflow。

## 下一人工门槛

W04最终精确head Gate通过后，需要用户只在GitHub UI：

1. 创建或确认 `notification-runtime`；
2. 不设置Required Reviewer；
3. 关闭可用的管理员绕过；
4. Selected branches and tags仅允许 `main`；
5. 添加Environment Secret `BARK_PUSH_URL`，值直接从Bark App粘贴到GitHub；
6. 不在聊天中提供Secret值。

收到配置元数据确认后，再决定是否执行一次精确确认、最多一条的live Bark测试。