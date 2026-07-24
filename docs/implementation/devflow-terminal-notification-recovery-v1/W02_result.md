# W02 结果：跨Generation稳定完成去重

```yaml
status: PASS
verified_head_sha: 6f068f4d5b368b70faf5dfc12bc69c9f4f0aae69
state_consistency: PASS:30096468742
test: PASS:30096468735
bark_requests: 0
secret_reads: 0
```

## 已实现

`Devflow Incident` 对COMPLETED同时维护：

```text
devflow-root:<generation-fingerprint>:COMPLETED
devflow-task-completed:<task-id>
```

处理顺序：

1. 按task ID concurrency串行；
2. 读取canonical Issue评论；
3. 任一marker已存在即停止，`should_push=false`；
4. 首次COMPLETED评论写入两种marker；
5. Bark Job只有 `should_push=true` 且Incident `run_attempt=1` 才运行。

这会阻止：

-同generation重复dispatch；
- producer Workflow重跑；
-新generation恢复通知；
-迟到旧generation；
-并发completion event。

非COMPLETED事件继续使用root-cause marker，不会被稳定完成marker误伤。

## 验收

通知清单、专用Validator和Workflow测试均覆盖stable marker。确定性Gate通过，真实Bark请求保持0。