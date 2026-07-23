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

## 去重与 ACK

每个任务使用一个控制 Issue：`[TASK CONTROL] <task-id>`。事件键：

```text
task_id + notification_type + notification_generation
```

同一事件不重复创建 Issue；在控制 Issue 追加一次 `@tyxq428` 评论并指派。状态流转：`OPEN → NOTIFIED → ACKNOWLEDGED → RESOLVED`。收到 `/ack` 或 canonical state 中的 ACK 后停止提醒。

## 内容

有价值通知必须包含：任务、阶段、状态、原因分类、Workflow Run、已经完成、最小人工动作、影响范围和 `HANDOFF.md` 恢复入口。不得包含 Secret、完整日志或未经裁剪的异常正文。

任务完成邮件只能在所有必做项和独立 post-merge 都通过后发送一次，不能把单个 Workflow 成功当作整个任务完成。
