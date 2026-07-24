# Handoff：Devflow Terminal Notification Recovery v1

## 当前检查点

- W00–W03已完成并有计划/结果；
- 独立completion producer、stable task marker、manifest、Validator、测试和文档已实现；
- 精确实现head `6f068f4d5b368b70faf5dfc12bc69c9f4f0aae69` 的Upgrade Compatibility、Test、State Consistency和真实688521 E2E全部PASS；
- Draft PR #58保持开放；
- Codex Policy保持disabled；
- 未调用Codex、Responses、Relay、历史模型Workflow或Bark；
- 未读取或显示Bark Secret。

## 当前阶段

```yaml
status: VERIFYING
stage: W04
last_completed_stage: W03
pull_request: 58
next_action:
  - wait_for_exact_PR_head_checks
  - inspect_only_failed_deterministic_checks
  - write_W04_result
  - persist_W05_plan_and_merge_state
  - run_final_exact_head_checks
  - mark_PR58_ready_and_merge
```

## 不要执行

- 不修改已完成旧任务的notification generation；
- 不重跑旧State Consistency、producer或Incident；
- 不通过UI Re-run补发；
- 不创建任意payload synthetic测试；
- 不读取或输出 `BARK_PUSH_URL`；
- 不让producer失败改变canonical任务结果；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。

## 合并后的真实验证

实现合并后使用独立closeout PR把本任务原子更新为DONE generation1。main State Consistency成功后，独立producer应产生可观察Run、一个canonical completion Issue、最多一个Bark POST和一个安全回执Artifact。