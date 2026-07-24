# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00–W04已完成并有计划/结果文档；
- Incident已泛化到任意登记任务，canonical Issue marker去重和单次Bark Transport已实现；
- canonical完成事件只在State Consistency全部Gate PASS后产生；
- 通知扫描、dispatch和Bark发送失败均为fail-open，不改变canonical任务结果，也不触发Auto Recovery；
- 失败类终态由Auto Recovery集中分类，Product Gate和Post Merge不再重复通知；
- 通知机器清单、永久Validator、策略和Runbook已完成；
- 精确PR head `16bb730900412d05adf9e634b4526629975d0f4a` 的四个确定性Gate全部PASS；
- Draft PR #54保持开放且未合并；
- Codex Policy保持 `disabled`；
- 未调用Codex、Responses、Relay或Bark；
- 未读取或配置任何Secret。

## 当前状态

```yaml
status: WAITING_HUMAN
execution_status: BLOCKED
stage: W05
last_completed_stage: W04
pull_request: 54
next_action: configure_notification_runtime_and_BARK_PUSH_URL_in_GitHub_UI
resume_from: docs/implementation/devflow-bark-terminal-notification-v1/W05_plan.md
```

## 唯一人工动作

在GitHub UI完成：

1. 创建或确认Environment `notification-runtime`；
2. 不设置Required Reviewer；
3. 关闭可用的管理员绕过；
4. Selected branches and tags仅允许 `main`；
5. 添加Environment Secret `BARK_PUSH_URL`；
6. Secret值使用Bark App复制的完整HTTPS推送URL；
7. 不在聊天、PR、Issue、日志或截图中显示该值。

## 不要执行

- 不监听所有 `workflow_run: completed`并直接通知；
- 不把 `BARK_PUSH_URL`写入仓库、Issue、PR、Artifact、聊天或日志；
- 不复用 `agent-runtime`；
- 不为通知失败触发Auto Recovery；
- 不自动重试Bark；
- 不在平台配置完成前发送真实Bark；
- 不在平台配置完成前合并PR #54；
- 不调用或测试Codex、Responses、Relay或历史模型Workflow。

## 恢复后的真实验证

不创建synthetic测试Workflow。本任务在合并和exact-main验证完成后更新为新的canonical DONE generation；随后State Consistency PASS触发唯一真实完成事件、canonical Issue和最多一条Bark。