# 有价值通知政策

## 核心规则

原始 Workflow 失败不能直接通知用户。所有失败必须先经过 `Devflow Auto Recovery` 的分类、有限重试、确定性修复或受限 Codex Recovery Generation。

只有以下最终决策可以进入 task-control Issue：

```text
[TASK][COMPLETED]
[TASK][INTERRUPTED]       # 自动恢复预算耗尽或无法安全分类
[TASK][HUMAN_REQUIRED]    # 确实需要用户配置、权限或业务决策
[TASK][SECURITY_BLOCKED]  # Secret、Scope或Manifest安全门禁失败
```

## 静默状态

以下全部静默，只写 Job Summary、Artifact 和 canonical state：

- `QUEUED / RUNNING / RETRYING`；
- 阶段开始和阶段完成；
- 普通测试、Targeted Gate、Full Gate、Secret Audit 和 E2E PASS；
- 缓存命中、分支 Push、Product Gate 接力；
- 基础设施失败 Job 的自动重跑；
- Codex Task Generation 的定向重跑；
- 一个受限 Codex Recovery Generation 的创建、执行和成功；
- 自动合并成功和 Post-Merge 启动。

## 单一控制 Issue

每个任务只使用一个控制 Issue：`[TASK CONTROL] <task-id>`。编号在自动通知启用前写入：

```text
task_state.yaml → notification.control_issue_number
```

Incident Workflow 只接受 `repository_dispatch: devflow_notify`，不得直接监听 `workflow_run`。Auto Recovery、Product Gate 和 Post-Merge 只有在确认需要通知时才发送该事件。

## 去重

去重键不是 Workflow Run ID，而是：

```text
task_id + root_cause_fingerprint + notification_type
```

同一根因导致多个 Workflow 或多个 Run 失败时，只能产生一次有价值通知。新的 notification generation 只有在根因变化、人工决策变化或任务最终完成时才允许追加。

## ACK 语义

`/ack` 只表示“用户已经看到通知”。它不会：

- 触发修复；
- 重跑 Workflow；
- 调用 Codex；
- 恢复或继续任务；
- 修改 canonical state。

自动恢复在通知发出前已经完成全部安全尝试。需要用户处理的通知必须明确写出最小人工动作；用户完成该动作后使用 `/resume` 或回到 ChatGPT Web 提交新的事实，而不是只回复 `/ack`。

## 内容

有价值通知必须包含：

- 任务和通知类型；
- 稳定原因分类和 root-cause fingerprint；
- 来源 Workflow、Run 和失败 Step；
- 已自动尝试的恢复路径；
- 剩余或已耗尽预算；
- 唯一最小人工动作；
- `HANDOFF.md` 恢复入口。

不得包含 Secret、完整日志、真实 Relay URL/hostname、模型 ID 或未经裁剪的异常正文。

## 完成通知

`[TASK][COMPLETED]` 只能在以下全部满足后发送一次：

- Codex/代码任务已通过 Targeted Gate；
- Full Product Gate 通过；
- 低风险任务已合并到 `main`；
- exact-main Post-Merge 通过；
- canonical state 已更新为 `DONE / COMPLETED / PASS`；
- `STATUS.md`、`HANDOFF.md`、阶段结果和 `FINAL_REPORT.md` 已生成并通过状态一致性检查。

完成通知写入后，canonical task-control Issue 可以关闭为 `completed`。
