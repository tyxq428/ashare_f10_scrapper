# Runbook：处理真正需要人工介入的 Incident

## 前提

控制 Issue 中出现通知时，`Devflow Auto Recovery` 已经完成所有安全的自动尝试。普通 Workflow 首次失败、基础设施重试和受限 Codex Recovery Generation 不会进入 Issue。

## 处理步骤

1. 在 canonical task-control Issue 中读取最新有价值通知，核对 `notification_type`、原因分类和 root-cause fingerprint。
2. 打开 `HANDOFF.md`、Failure Bundle、对应 Run/Job 和失败测试；完整日志仅在需要时定向读取。
3. 核对通知是否属于：
   - `HUMAN_REQUIRED`：需要 Secret、权限、验证码、业务选择或合并边界；
   - `SECURITY_BLOCKED`：Secret、Scope、Manifest 或不可信输入；
   - `INTERRUPTED`：自动恢复预算耗尽或无法安全分类；
   - `COMPLETED`：无动作，Issue 将关闭。
4. 只执行通知中给出的最小人工动作，不要无差别重跑全部 Workflow。
5. 完成人工动作后：
   - 外部配置/权限已修复：使用 `/resume` 或在 ChatGPT Web 明确说明已完成的事实；
   - 业务决策：把唯一决定写入 `DECISIONS.md` 再恢复；
   - 安全阻断：完成调查和凭据处置后才允许恢复；
   - 需要扩大代码范围：由 ChatGPT Web 生成新的任务合同和 Task Descriptor。
6. 将通用工程问题追加到 `ENGINEERING_ISSUES_AND_LESSONS.md`，包含现象、根因、修复、预防规则和回归检测。
7. 更新 canonical state、HANDOFF 和 Incident 状态，再从稳定检查点恢复。

## `/ack` 的准确含义

`/ack` 只表示“我已看到”。它不会触发：

- 自动修复；
- 重跑；
- Codex；
- `/resume`；
- canonical state 更新。

因此正常可自动恢复的故障不会要求用户 `/ack`；只有已经需要人工注意的通知才显示 ACK 语义。

## 判断是否已解决

不要依赖 ChatGPT 页面中的思考动画。按顺序核对：

1. `task_state.yaml`；
2. 最新 Workflow conclusion；
3. 产品 Merge SHA；
4. `HANDOFF.md.next_action`；
5. `FINAL_REPORT.md`。

只有 `DONE / COMPLETED / PASS` 且 exact-main Post-Merge 已记录，才算最终解决。
