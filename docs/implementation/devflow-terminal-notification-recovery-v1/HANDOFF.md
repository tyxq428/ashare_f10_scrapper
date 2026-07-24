# Handoff：Devflow Terminal Notification Recovery v1

## 当前检查点

- W00–W04已完成并有计划/结果；
- 独立completion producer、stable task marker、manifest、Validator、测试和文档已实现；
- W04精确head `f7431c16262cd98e790038316af11ef10e126f2c` 的四个Gate全部PASS；
- Draft PR #58保持开放；
- Codex Policy保持disabled；
- 未调用Codex、Responses、Relay、历史模型Workflow或Bark；
- 未读取或显示Bark Secret。

## 当前阶段

```yaml
status: VERIFYING
stage: W05
last_completed_stage: W04
pull_request: 58
next_action:
  - wait_for_final_exact_head_checks
  - recheck_open_PR_overlap
  - mark_PR58_ready
  - merge_PR58
  - verify_exact_main_source
  - create_atomic_closeout_PR
  - observe_single_real_Bark_and_receipt
```

## 不要执行

- 不修改已完成旧任务的notification generation；
- 不重跑旧State Consistency、producer或Incident；
- 不通过UI Re-run补发；
- 不创建任意payload synthetic测试；
- 不读取或输出 `BARK_PUSH_URL`；
- 不让producer失败改变canonical任务结果；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。

## 实现合并后的恢复入口

1.核验implementation merge SHA和exact-main源码；
2.从implementation main创建独立closeout PR；
3.原子更新DONE state、FINAL_REPORT、STATUS、HANDOFF和ACTIVE_TASKS；
4.closeout main State Consistency成功；
5.独立producer运行并dispatch；
6.canonical Issue stable marker只出现一次；
7.Incident最多执行一个Bark POST并上传安全回执；
8.下载并validate回执；
9.纯文档观察PR记录实际结果，不修改task state或generation。