# W04 计划：精确PR Head验证与实现合并准备

## 目标

把实现分支推进到可安全合并状态，并保证合并后main上的canonical active task仍满足state规则，且不会在实现合并时提前发送Bark。

## 状态准备

在最终实现head中设置：

```yaml
status: VERIFYING
execution_status: RUNNING
current_stage: W05
last_completed_stage: W04
working_branch: feature/devflow-bark-delivery-receipt-v1
notification:
  generation: 0
  last_type: null
  acknowledged: true
```

这样PR #56合并后：

- active task在main上处于W05，符合合并/closeout阶段规则；
- 不产生新的`COMPLETED` generation；
- 不发起Bark；
- 后续closeout PR可以原子进入DONE。

## 最终PR Head Gate

对包含所有实现、守卫、文档和状态准备的精确head运行：

1. Devflow Upgrade Compatibility；
2. Test；
3. Devflow State Consistency；
4. 真实E2E 688521。

全部PASS后才允许：

- 将PR #56转为Ready；
- 审核并行PR路径交集；
- 合并PR #56。

## 合并后

- 核验implementation merge SHA；
- 确认Codex Policy仍为disabled；
- 确认main中只有一个Bark POST和一个回执Artifact上传位置；
- 创建独立closeout分支和PR；
- closeout前真实Bark请求仍为0。

## Gate

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_live_requests_before_closeout: 0
```