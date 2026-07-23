# Runbook：处理 Incident

1. 在同一任务控制 Issue 中读取最新有价值通知，核对事件代次和 ACK 状态。
2. 打开 `HANDOFF.md`、Failure Bundle、对应 Run/Job 和失败测试；完整日志仅在需要时定向读取。
3. 确认执行状态与研究验收状态没有混用。
4. 分类处理：
   - `INFRA_RETRYABLE`：只重跑失败 Job/步骤；
   - `MECHANICAL`：同版本工具修复并补测试；
   - `IMPLEMENTATION`：Web 形成新的最小修复任务；
   - `SECURITY_BLOCKED`：停止发布、吊销相关任务、完成泄漏调查；
   - `PERMISSION/BUSINESS_DECISION`：请求最小人工动作。
5. 将通用工程问题追加到 `ENGINEERING_ISSUES_AND_LESSONS.md`，包含现象、根因、修复、预防规则和回归检测。
6. 更新 state、HANDOFF 和 Incident 状态。收到 `/ack` 后停止升级；解决后标记 `RESOLVED` 并从检查点继续。
