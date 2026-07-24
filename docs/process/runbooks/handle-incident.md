# Runbook：处理真正需要人工介入的Incident

## 前提

控制Issue或Bark出现通知时，`Devflow Auto Recovery` 已经完成所有安全的自动尝试。普通Workflow首次失败、基础设施重试和确定性修复不会进入通知总线。

Bark只是即时提醒；canonical task-control Issue和 `task_state.yaml` 才是权威记录。Bark未送达不表示任务仍在运行，Bark送达也不能替代canonical状态核验。

## 处理步骤

1. 从Bark点击仓库内目标URL，或直接打开canonical task-control Issue；不要依据通知正文执行高风险动作。
2. 在Issue中读取最新有价值通知，核对 `notification_type`、原因分类和root-cause fingerprint。
3. 打开 `HANDOFF.md`、Failure Bundle、对应Run/Job和失败测试；完整日志仅在需要时定向读取。
4. 核对通知是否属于：
   - `HUMAN_REQUIRED`：需要Secret、权限、验证码、业务选择或合并边界；
   - `SECURITY_BLOCKED`：Secret、Scope、Manifest或不可信输入；
   - `INTERRUPTED`：自动恢复预算耗尽或无法安全分类；
   - `COMPLETED`：无动作，Issue将关闭。
5. 只执行通知中给出的最小人工动作，不要无差别重跑全部Workflow。
6. 完成人工动作后：
   - 外部配置/权限已修复：使用 `/resume` 或在ChatGPT Web明确说明已完成的事实；
   - 业务决策：把唯一决定写入 `DECISIONS.md` 再恢复；
   - 安全阻断：完成调查和凭据处置后才允许恢复；
   - 需要扩大代码范围：由ChatGPT Web生成新的任务合同和Task Descriptor。
7. 将通用工程问题追加到 `ENGINEERING_ISSUES_AND_LESSONS.md`，包含现象、根因、修复、预防规则和回归检测。
8. 更新canonical state、HANDOFF和Incident状态，再从稳定检查点恢复。

## 核验Bark投递回执

当Issue出现 `[BARK][DELIVERY_RECEIPT]` 时：

1. 核对评论中的Task和notification type与该Issue一致；
2. 打开评论中的Incident Run；
3. 记录Artifact ID并下载 `bark-delivery-receipt-<task-id>-<run-id>`；
4. ZIP内只应存在一个 `bark-delivery-result.json`；
5. 在可信checkout中运行：

```bash
python scripts/devflow/bark_delivery_result.py validate \
  --input bark-delivery-result.json
```

6. 解释结果：
   - `DELIVERED`：已发起1次请求，curl成功且服务端返回HTTP 2xx；
   - `FAILED`：已发起1次请求，但网络/curl或HTTP没有成功；
   - `SKIPPED_MISSING_CONFIGURATION`：未发起请求，检查 `notification-runtime` 配置；
7. 同时确认：
   - `automatic_retry=false`；
   - response body/headers、Endpoint、Secret和raw error全部未保存；
   - Incident run attempt为1；
   - request attempts为0或1。

Artifact与回执评论只是观察证据。Artifact上传失败、评论失败、Artifact过期或缺失时：

- 不得推断Bark一定未发送；
- 不得撤销canonical终态；
- 不得通过UI Re-run补发；
- 应以canonical Issue marker、task state和已有Job Summary为权威事实，并只修复未来通知。

## Bark未到或重复检查

- 首先检查canonical Issue；marker存在说明逻辑通知已经记录；
- 检查是否存在 `[BARK][DELIVERY_RECEIPT]`，以 `request_initiated` 和Transport状态判断正向证据；
- Bark采用at-most-once且无自动重试，网络不确定时不会再次推送；
- 不要通过GitHub UI Re-run尝试补发，`run_attempt > 1` 会阻止Bark请求；
- 不要把 `BARK_PUSH_URL` 粘贴到聊天、Issue或日志；
- 需要修复通知配置时，只在 `Settings → Environments → notification-runtime` 操作；
- 通知配置、Artifact或索引失败不应触发Auto Recovery，也不应修改任务终态。

## `/ack` 的准确含义

`/ack` 只表示“我已看到”。它不会触发：

- 自动修复；
- 重跑；
- Codex；
- `/resume`；
- canonical state更新；
- Bark补发。

因此正常可自动恢复的故障不会要求用户 `/ack`；只有已经需要人工注意的通知才显示ACK语义。

## 判断是否已解决

不要依赖ChatGPT页面中的思考动画或Bark投递结果。按顺序核对：

1. `task_state.yaml`；
2. 最新Workflow conclusion；
3. 产品Merge SHA；
4. `HANDOFF.md.next_action`；
5. `FINAL_REPORT.md`；
6. canonical Issue中的唯一marker；
7. 可用时核验安全Bark回执Artifact，但它不决定任务终态。

只有 `DONE / COMPLETED / PASS` 且exact-main已记录，才算最终解决。