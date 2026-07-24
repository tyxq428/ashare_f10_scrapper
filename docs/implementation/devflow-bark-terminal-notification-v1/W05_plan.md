# W05 计划：notification-runtime平台配置、合并与真实完成通知

## 阶段入口

W00–W04实现与确定性Gate已全部通过。W05只处理GitHub平台配置、PR合并、exact-main验证和本任务自身的真实完成通知。

## 唯一人工配置

在GitHub仓库页面执行：

```text
Settings
→ Environments
→ New environment（或打开已有环境）
→ notification-runtime
```

配置：

1. **Required reviewers**：不配置；终态通知必须在任务完成后自动发送；
2. **Prevent self-review**：不适用，因为无Required Reviewer；
3. **Allow administrators to bypass configured protection rules**：若页面提供，关闭；
4. **Deployment branches and tags**：Selected branches and tags，仅允许 `main`；
5. **Environment secrets**：新增 `BARK_PUSH_URL`；
6. Secret值必须是Bark App复制的完整HTTPS推送URL；
7. 只在GitHub UI粘贴Secret，不在聊天、PR、Issue、日志或Artifact中显示。

不需要向ChatGPT提供URL、Device Key、hostname或截图中的Secret内容。

## 人工确认格式

用户只需回复：

```text
notification-runtime 已创建或确认：无 Required Reviewer、管理员绕过已关闭、仅允许 main；BARK_PUSH_URL 已在 GitHub UI 配置，Secret 未在聊天或日志中显示。
```

## 恢复后动作

1. 记录平台元数据确认，不读取Secret；
2. 将PR #54转为Ready；
3. 对恢复后的精确PR head再次确认四个Gate；
4. 合并PR #54；
5. 在精确main上等待Test、State Consistency、Upgrade Compatibility和真实688521 E2E；
6. 写W05结果、FINAL_REPORT并将canonical state更新为 `DONE / COMPLETED / PASS`；
7. final state push触发State Consistency；
8. State Consistency PASS后产生本任务唯一真实 `COMPLETED` 事件；
9. Incident写入并关闭canonical Issue，然后通过 `notification-runtime`发送最多一条Bark；
10. 检查Incident Job的安全结论：HTTP 2xx或fail-open；不读取响应正文或Secret。

## Live验证策略

不创建独立synthetic test Workflow。本任务自身的最终 `COMPLETED` 通知即为一次真实端到端验证：

```text
canonical DONE generation
→ State Consistency PASS
→ repository_dispatch devflow_notify
→ canonical Issue marker
→ one Bark POST
```

这样避免永久测试按钮、额外触发面和无业务意义的重复推送。

## 失败语义

- Bark HTTP失败不撤销DONE、不重跑、不触发Auto Recovery；
- canonical Issue和task state仍是权威结果；
- 由于at-most-once策略，不通过UI Re-run补发；
- 若配置错误，只修复未来通知配置，不修改已完成任务事实；
- 若State Consistency或产品Gate失败，则不进入完成通知，先确定性修复。

## 最终预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
production_completion_bark_requests_max: 1
bark_automatic_retries: 0
```