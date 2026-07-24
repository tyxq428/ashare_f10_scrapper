# W04 计划：精确PR Head验证与实现合并

## 状态准备

最终实现PR head将canonical task推进为：

```yaml
status: VERIFYING
execution_status: RUNNING
current_stage: W05
last_completed_stage: W04
notification:
  generation: 0
  last_type: null
  acknowledged: true
```

因此实现合并不会生成completion event或Bark请求。

## 完整Gate

对最终精确head运行：

1. Devflow Upgrade Compatibility；
2. Test；
3. Devflow State Consistency；
4. 真实E2E 688521。

## 合并前检查

- 当前只有本PR开放；
- 并行开放PR路径交集为0；
- Codex Policy仍为disabled；
- Bark POST位置仍为1；
- scanner producer仍为1；
- receipt Artifact上传位置仍为1；
- Bark请求仍为0。

## 合并后

-记录implementation merge SHA；
-验证merge tree相对测试head无文件差异；
-从exact main创建独立closeout PR；
-closeout才产生本任务唯一COMPLETED generation。

## Gate

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_requests_before_closeout: 0
```