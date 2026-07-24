# 决策记录

## D001｜通知任务终态，不通知原始 Workflow 结束

Bark 只接收 `COMPLETED / INTERRUPTED / HUMAN_REQUIRED / SECURITY_BLOCKED`。普通 Workflow success/failure、阶段完成、重试和确定性修复继续静默。禁止让 Incident 直接监听 raw `workflow_run`。

## D002｜Bark 是辅助通道

`task_state.yaml` 和 canonical task-control Issue 继续作为权威状态与持久记录。Bark 发送失败不得改变任务状态，也不得撤销已完成结果。

## D003｜独立 Secret 边界

使用 `notification-runtime` Environment 和 `BARK_PUSH_URL`，不复用 `agent-runtime`，不读取或复制 Relay Secret。通知 Job 只需 `contents: read`。

## D004｜At-most-once 投递

每条逻辑通知最多一次 Bark HTTP 请求，不自动重试。`github.run_attempt > 1` 时禁止发送；逻辑重复事件复用 canonical Issue marker 去重。

## D005｜完成事件比中断事件更严格

`COMPLETED` 必须与 canonical `DONE / COMPLETED / PASS`、`security_status=PASS`、`post_merge=PASS` 和无 human gate 一致。中断、人工和安全事件必须来自既有确定性分类或显式终止路径。

## D006｜不用 synthetic Workflow 测试 Bark

不增加永久或临时的 Bark 测试按钮。本任务自身在 PR #54 合并、exact-main Gate 通过并进入新的 canonical DONE generation 后，产生唯一真实 `COMPLETED` 事件并尝试最多一次 Bark。这样避免额外触发面和无业务意义的测试推送。

## D007｜平台配置由用户在 GitHub UI 完成

用户已确认：`notification-runtime` 无 Required Reviewer；可用的管理员绕过已关闭；Selected branches and tags 仅允许 `main`；Environment Secret `BARK_PUSH_URL` 已直接在 GitHub UI 配置。Secret 值没有在聊天、仓库、PR、Issue、日志或 Artifact 中显示。

## D008｜平台确认不等于读取 Secret

后续流程只记录配置元数据事实，不读取、下载、回显或复制 `BARK_PUSH_URL`。真实验证只观察 Incident/Bark Job 的安全结论和 HTTP 接受状态；响应正文与 endpoint 诊断均不保存。
