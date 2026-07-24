# 决策记录

## D001｜通知任务终态，不通知原始 Workflow结束

Bark只接收 `COMPLETED / INTERRUPTED / HUMAN_REQUIRED / SECURITY_BLOCKED`。普通 Workflow success/failure、阶段完成、重试和确定性修复继续静默。禁止让 Incident直接监听 raw `workflow_run`。

## D002｜Bark是辅助通道

`task_state.yaml` 和 canonical task-control Issue继续作为权威状态与持久记录。Bark发送失败不得改变任务状态，也不得撤销已完成结果。

## D003｜独立 Secret边界

使用 `notification-runtime` Environment和 `BARK_PUSH_URL`，不复用 `agent-runtime`，不读取或复制 Relay Secret。通知 Job只需 `contents: read`。

## D004｜At-most-once投递

每条逻辑通知最多一次 Bark HTTP请求，不自动重试。`github.run_attempt > 1` 时禁止发送；逻辑重复事件复用 canonical Issue marker去重。

## D005｜完成事件比中断事件更严格

`COMPLETED` 必须与 canonical `DONE / COMPLETED / PASS`、`security_status=PASS`、`post_merge=PASS` 和无 human gate一致。中断、人工和安全事件必须来自既有确定性分类或显式终止路径。

## D006｜平台配置后再做 live test

开发、PR Gate和 mock测试阶段真实 Bark请求数保持0。只有用户在 GitHub UI完成 `notification-runtime` 与 Secret配置后，才允许一次带精确确认短语的 live test，成功后删除临时测试 Workflow。