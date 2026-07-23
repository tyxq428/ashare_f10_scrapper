# 决策记录：chatgpt-web-codex-devflow-v1

| ID | 决策 | 理由 |
|---|---|---|
| D-001 | 使用 ChatGPT Web Supervisor + Actions Executor + Codex Thin Worker | 保留 Web 高上下文规划能力，同时让后台完成窄代码任务 |
| D-002 | 私有 Relay URL、Key、模型 ID 均使用 Environment Secrets | Public 仓库不公开配置 |
| D-003 | Codex 只连接 localhost Forwarder | 避免 Codex 参数和错误日志出现真实上游 URL |
| D-004 | Secret Job 只读、Publish Job 无 Secret | 凭据与仓库写权限分离 |
| D-005 | Codex 每任务一次 Session、显式 low effort | 固定成本、避免无限修复和行为漂移 |
| D-006 | PR 由 ChatGPT Web 创建和控制 | 不扩大 Actions 创建 PR/合并权限 |
| D-007 | canonical state 使用 JSON 语法的 `.yaml` | JSON 是 YAML 子集，可用 Python 标准库确定性解析 |
| D-008 | 原 SOP v2 作为迁移输入，长期权威拆为 Policies/Runbooks/Templates | 降低重复上下文和规则漂移 |
| D-009 | 只通知完成、中断、人工和安全状态 | 降低 Actions 邮件噪声 |
| D-010 | PR-A 与真实薄切片 PR-B 分离 | 基础设施先合并并独立验证，再使用自身执行真实代码修改 |
