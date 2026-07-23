# 有价值通知政策

## 发送邮件/Issue 的状态

只发送：

```text
[TASK][COMPLETED]
[TASK][INTERRUPTED]
[TASK][HUMAN_REQUIRED]
[TASK][SECURITY_BLOCKED]
```

## 静默状态

`QUEUED`、`RUNNING`、`RETRYING`、阶段完成、普通测试 PASS、缓存命中、分支 Push、PR 更新、Secret Audit PASS 和中间 E2E PASS 全部静默，只写 Job Summary、Artifact 和 canonical state。

## 单一控制 Issue

每个任务只使用一个控制 Issue：`[TASK CONTROL] <task-id>`。该 Issue 必须在启用自动通知前由 ChatGPT Web Supervisor 创建，并把编号写入：

```text
task_state.yaml → notification.control_issue_number
```

Incident Workflow 必须优先使用这个固定编号，并验证 Issue 标题与任务 ID 一致。不得在正常执行中反复按标题推断或创建新 Issue。缺少 canonical issue number 时，只允许使用带串行保护的兜底创建流程，并应尽快由 Web Supervisor把编号回写 canonical state。

## 去重与 ACK

事件键：

```text
task_id + workflow_run_id + notification_type
```

同一事件不得重复评论。Incident Workflow 在固定控制 Issue 中追加一次 `@tyxq428` 评论并保持指派。状态流转：`OPEN → NOTIFIED → ACKNOWLEDGED → RESOLVED`。收到 `/ack` 或 canonical state 中的 ACK 后停止提醒。

任务最终完成且完成通知已写入后，可以把控制 Issue 关闭为 completed。中断、人工介入和安全阻断状态下不得自动关闭。

## 内容

有价值通知必须包含：任务、阶段、状态、原因分类、Workflow Run、已经完成、最小人工动作、影响范围和 `HANDOFF.md` 恢复入口。不得包含 Secret、完整日志或未经裁剪的异常正文。

任务完成邮件只能在所有必做项和独立 post-merge 都通过后发送一次，不能把单个 Workflow 成功当作整个任务完成。
