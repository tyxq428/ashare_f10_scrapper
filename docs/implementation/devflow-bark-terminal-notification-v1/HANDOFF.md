# Handoff：Devflow Bark Terminal Notification v1

## 当前检查点

- W00–W02已完成并有结果文档；
- W03已实现canonical完成生产者、集中式失败分类、task ID绑定和永久通知触发面Validator；
- Incident已泛化到任意登记任务，Issue marker去重和单次Bark Transport已实现；
- 通知政策、Incident Runbook和机器可读控制清单已更新；
- Draft PR #54已创建，正在等待精确head确定性Gate；
- Codex Policy保持 `disabled`；
- 未调用 Codex、Responses、Relay或 Bark；
- 未读取或配置任何 Secret。

## 当前阶段

```yaml
stage: W03
last_completed_stage: W02
pull_request: 54
next_action:
  - wait_for_exact_PR_head_checks
  - inspect_only_failed_deterministic_checks
  - fix_without_model_or_paid_probe
  - write_W03_result
  - persist_W04_plan_before_premerge_verification
```

## 不要执行

- 不监听所有 `workflow_run: completed`并直接通知；
- 不把 `BARK_PUSH_URL`写入仓库、Issue、PR、Artifact或日志；
- 不复用 `agent-runtime`；
- 不为Bark失败触发Auto Recovery；
- 不自动重试Bark；
- 不在配置完成前发送真实Bark；
- 不调用或测试Codex、Responses或历史模型Workflow。

## 预期人工门槛

代码和确定性Gate通过后，需要用户在GitHub UI创建/确认 `notification-runtime`并添加 `BARK_PUSH_URL`。Secret值不得通过聊天传递。