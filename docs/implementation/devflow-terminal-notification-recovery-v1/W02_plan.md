# W02 计划：跨Generation稳定完成去重

## 目标

确保同一task即使出现Workflow重跑、恢复generation或迟到旧event，也只允许一个完成Issue和一个Bark请求。

## Marker

保留精确审计marker：

```text
devflow-root:<generation-fingerprint>:COMPLETED
```

新增稳定task marker：

```text
devflow-task-completed:<task-id>
```

## Incident行为

- COMPLETED事件先读取canonical Issue全部评论；
- generation marker或stable marker任一存在即`should_push=false`；
- 首次COMPLETED评论同时写入两种marker；
- 非COMPLETED事件不写stable marker；
- concurrency继续按task ID序列化；
- Bark Job仍要求`should_push=true`和`run_attempt=1`。

## 测试

- Incident包含两marker检查；
- COMPLETED评论包含stable marker；
-重复generation marker阻止Bark；
-不同generation但同task的stable marker阻止Bark；
-非COMPLETED不被跨类型错误去重；
-无稳定marker时首次COMPLETED仍可进入Bark。

## Gate

```yaml
static_validator: PASS_required
workflow_tests: PASS_required
bark_requests: 0
secret_reads: 0
```