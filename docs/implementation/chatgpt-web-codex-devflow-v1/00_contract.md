# 任务合同：ChatGPT Web + Actions + Codex Thin Worker

## 目标

把现有由 ChatGPT Web 驱动的开发方式升级为可持续、可恢复、可审计的执行流：ChatGPT Web 负责规划、诊断、审查和决策；GitHub Actions 负责确定性执行、Gate、Artifact 和状态事件；Codex 仅在明确边界内修改代码。

## 交付范围

1. 将 SOP v2 拆为分层指令；
2. 建立根级与 Scoped `AGENTS.md`；
3. 建立 Policies、Runbooks、Templates 和动态任务状态；
4. 建立 reusable Codex Thin Worker；
5. 建立状态一致性、Gate、Incident、Secret Audit、Relay Health 和 post-merge 流程；
6. 在正式仓库完成一个真实低风险 Codex 薄切片；
7. 定义后续任务的渐进迁移标准。

## 角色边界

- **ChatGPT Web Supervisor**：总计划、任务拆分、错误诊断、PR 控制、合并与最终验收。
- **GitHub Actions Executor**：环境、脚本、测试、Gate、Patch 交接、通知事件和审计。
- **Codex Thin Worker**：读取任务包和允许文件，完成一次受限编辑，不决定项目路线。
- **用户**：只处理真实权限、安全、不可逆风险或业务口径决策。

## 安全约束

- 正式仓库为 Public，但真实中转站 URL、hostname、Key 和模型 ID 均不得公开；
- Secret 只存在于 `agent-runtime` Environment；
- Codex 通过 localhost forwarder 访问上游；
- Secret Job 只读，Publish Job 无 Secret；
- 所有 Artifact 和公共日志执行独立泄漏审计；
- 不自动合并，不从不可信 PR、Issue 或评论触发 Codex。

## 完成标准

PR-A 基础设施和 PR-B 真实薄切片均合并且 post-merge Gate 通过；Secret Audit、状态一致性和中断通知均通过；集中经验库和最终报告完成；后续迁移标准明确。
