# 有价值通知政策

## 核心规则

原始 Workflow 失败不能直接通知用户。所有失败必须先经过 `Devflow Auto Recovery` 的分类、有限重试或确定性修复边界。

只有以下最终决策可以进入通知总线：

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
- 确定性修复和重新验证；
- 自动合并成功和 Post-Merge 启动。

## 双通道模型

每条有价值通知通过同一个 `repository_dispatch: devflow_notify` 事件进入 `Devflow Incident`，然后分发到：

1. **canonical task-control Issue**：权威、持久、可查询的通知记录；
2. **Bark**：辅助的即时手机提醒。

Bark不是状态源。Bark缺少配置、网络失败或服务端不可用时，不得撤销已经完成的任务、改变canonical state、触发Auto Recovery或再次发送同一通知。

## 单一控制 Issue

每个任务只使用一个控制 Issue：`[TASK CONTROL] <task-id>`。

优先使用：

```text
task_state.yaml → notification.control_issue_number
```

若canonical state尚未持久化Issue编号，Incident只能按精确标题查找非PR Issue；没有匹配时创建一个，多个匹配时Fail Closed。Incident不得修改仓库状态文件来记录Issue编号。

Incident Workflow只接受 `repository_dispatch: devflow_notify`，不得直接监听 `workflow_run`。失败类事件由Auto Recovery完成分类后发送；成功路径中的明确人工门槛可以携带显式task ID直接发送。

## 完成事件生产

`COMPLETED` 不从普通 Workflow success直接产生。`Devflow State Consistency` 在 `main` 上完成全部state、Workflow、文档、Ruff和pytest校验后，才由独立的 `notify-terminal-state` Job扫描本次push中的canonical task state变化。只有以下条件全部成立才进入通知总线：

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
post_merge: PASS
human_gate.required: false
notification.last_type: COMPLETED
notification.acknowledged: false
notification.generation: increased
active_tasks.status: DONE
completion_source: Devflow State Consistency
```

完成事件的fingerprint必须精确绑定当前canonical notification generation。伪造generation、在State Consistency通过前直接dispatch或在任务DONE后发送其他终态类型均Fail Closed。

完成通知的扫描与dispatch属于辅助通知阶段，必须fail-open，不能把已经通过的State Consistency或任务终态重新标记失败，也不能进入Auto Recovery。Workflow重跑会产生相同fingerprint；Incident marker去重后不得重复写Issue或发送Bark。

## 去重

去重键不是 Workflow Run ID，而是：

```text
task_id + root_cause_fingerprint + notification_type
```

同一根因导致多个 Workflow 或多个 Run 失败时，只能产生一次有价值通知。新的 notification generation只有在根因变化、人工决策变化或任务最终完成时才允许追加。

Incident先把marker持久化到canonical Issue，再允许Bark Job运行。因此系统采用 **at-most-once** Bark语义：不会自动重试；极少数“服务端已收到但客户端未收到响应”的不确定场景也不会冒险重复推送。

## Bark安全边界

```yaml
environment: notification-runtime
secret: BARK_PUSH_URL
run_attempt_must_equal: 1
maximum_requests_per_notification: 1
automatic_retry: false
failure_changes_task_state: false
```

要求：

- `notification-runtime` 与 `agent-runtime` 完全分离；
- Bark完整推送URL只存放在Environment Secret，不得出现在仓库、Issue、PR、日志或Artifact；
- 只有 `Devflow Incident` 可以引用该Environment和Secret；
- Bark Job从可信 `main` 重新验证payload并生成裁剪后的JSON；
- 每条逻辑通知只有一个HTTP POST位置，响应正文不输出、不归档；
- GitHub UI Re-run因 `run_attempt != 1`不能重新发送；
- Auto Recovery不得监听Incident或Bark Job；
- 完成事件生产者不读取Bark Secret，也不直接执行HTTP请求。

## ACK语义

`/ack` 只表示“用户已经看到通知”。它不会：

- 触发修复；
- 重跑 Workflow；
- 调用 Codex；
- 恢复或继续任务；
- 修改 canonical state。

自动恢复在通知发出前已经完成全部安全尝试。需要用户处理的通知必须明确写出最小人工动作；用户完成该动作后使用 `/resume` 或回到 ChatGPT Web提交新的事实，而不是只回复 `/ack`。

## 内容

有价值通知必须包含：

- 任务和通知类型；
- 稳定原因分类和 root-cause fingerprint；
- 来源 Workflow、Run 和失败 Step；
- 已自动尝试的恢复路径；
- 剩余或已耗尽预算；
- 唯一最小人工动作；
- `HANDOFF.md` 恢复入口。

不得包含 Secret、完整日志、真实 Relay URL/hostname、模型 ID、Bark推送URL或未经裁剪的异常正文。

## 完成通知

`[TASK][COMPLETED]` 只能在以下全部满足后发送一次：

- 代码和目标Gate已通过；
- Full Product Gate通过；
- 任务已合并到 `main`；
- exact-main验证通过；
- canonical state已更新为 `DONE / COMPLETED / PASS`；
- `STATUS.md`、`HANDOFF.md`、阶段结果和 `FINAL_REPORT.md` 已生成；
- `Devflow State Consistency` 已在该精确main SHA上通过。

完成通知写入后，canonical task-control Issue可以关闭为 `completed`。Bark发送结果不影响该关闭动作。