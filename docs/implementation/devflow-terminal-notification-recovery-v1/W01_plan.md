# W01 计划：独立 State Consistency 成功后继Producer

## 目标

建立单一、独立、可观察的completion producer，并从State Consistency本体移除通知dispatch。

## 新Workflow

```text
.github/workflows/devflow-terminal-state-notify.yml
```

触发：

```yaml
workflow_run:
  workflows:
    - Devflow State Consistency
  types:
    - completed
```

Job入口必须同时满足：

```yaml
source_conclusion: success
source_event: push
source_head_branch: main
```

## 精确源码边界

- checkout `github.event.workflow_run.head_sha`；
- fetch-depth 2以上；
- fetch origin/main；
-验证source head SHA格式；
-验证source head是origin/main祖先；
- before SHA使用source head第一父提交；
- scanner的source_run_id使用原State Consistency Run ID；
- producer自身不读Secret、不运行Bark。

## Dispatch

复用 `terminal_notification_scan.py` 输出；每个event包装为 `repository_dispatch: devflow_notify`。

生产与dispatch步骤均：

- `continue-on-error: true`；
- 最终summary标记fail-open；
- 不触发Auto Recovery；
- 不创建Artifact；
- 不允许任意输入。

## State Consistency变更

删除 `notify-terminal-state` Job，只保留验证Job。这样仓库只有一个完成producer。

## 稳定去重

`notification_event.py` 为COMPLETED返回：

```yaml
marker: devflow-root:<generation-fingerprint>:COMPLETED
completion_marker: devflow-task-completed:<task-id>
```

Incident先检查两者任一是否存在。COMPLETED评论写入两者；非COMPLETED只有generation/root marker。

## 测试

- producer触发和筛选；
-精确source SHA和第一父提交；
-State Consistency无dispatch；
-Producer零Secret/零Bark；
-single producer；
-stable marker跨generation；
-Incident两marker去重；
-Auto Recovery不监听producer。

## Gate

```yaml
workflow_yaml_parse: PASS_required
validator: PASS_required
pytest: PASS_required
bark_requests: 0
secret_reads: 0
```