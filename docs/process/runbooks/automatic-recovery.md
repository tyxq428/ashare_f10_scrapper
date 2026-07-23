# Runbook：自动恢复、自动继续与通知升级

## 输入

`Devflow Auto Recovery` 接收受管 Workflow 的终态，并读取：

- Workflow name、Run ID、Run attempt 和 conclusion；
- Job/Step 名称与 conclusion；
- 安全摘要 Artifact；
- 可用时的 immutable `.agent/current_task.yaml`；
- canonical recovery budget。

不读取或输出 Relay URL、Key、模型 ID、完整环境或原始 HTTP 日志。

## 分类结果

| Action | 系统动作 | 用户通知 |
|---|---|---|
| `NOOP` | 无动作 | 否 |
| `RETRY` | 重跑失败 Job | 否 |
| `RETRY_CODEX` | 同一 Task Generation 定向重跑一次失败 Codex Job | 否 |
| `CODEX_REPAIR` | 创建一个受限 Recovery Generation | 否 |
| `HUMAN_REQUIRED` | 停止并给出唯一人工动作 | 是 |
| `SECURITY_BLOCKED` | 阻止发布和自动恢复 | 是 |
| `INTERRUPTED` | 预算耗尽或无法安全分类 | 是 |
| `COMPLETED` | 自动收尾并通知 | 是，1次 |

## 基础设施恢复

- `cancelled / timed_out / stale / startup_failure`；
- checkout、setup、依赖安装；
- Artifact 上传/下载；
- Relay 的临时 transport/protocol 错误。

在 run attempt 小于 3 时只调用 `rerun-failed-jobs`。成功后自动进入原 Workflow 后续逻辑；不创建 Issue 评论。

## Codex 恢复

- 同一 Task Generation 仍坚持 `session_limit=1`；
- 所有新的模型调用固定使用 `xhigh`；
- 失败 Job 可以按策略重跑一次；
- Targeted/Full/Post-Merge Gate 失败时最多创建一个新的 Recovery Generation；
- 新 generation 继承 allowed files、forbidden patterns、Gate、risk class 和 auto-merge policy；
- 新 generation 不允许自动扩大上下文或修改 Workflow/Secrets。

## Product Gate

Publish 成功后显式发送 `devflow_product_gate`：

1. 从控制分支读取 immutable descriptor，并确认 `expected_base_sha` 是候选分支祖先；
2. 计算候选分支与当前 `main` 的 Merge Base，只校验 Merge Base 到候选 HEAD 的新增路径；
3. 真实 Scope Violation时 Fail Closed、上传仅含路径的摘要，并进入 `SECURITY_BLOCKED`；
4. Scope通过后运行 Full Gate；
5. Full Gate失败且有预算时创建使用 `xhigh` 的 Recovery Generation；
6. Full Gate通过且批准低风险自动合并时，先固定 Git 提交身份为 `github-actions[bot]`；
7. 若 `main` 已推进则 rebase，并再次以最新 `origin/main` 校验 Scope、重跑 Full Gate；
8. 使用受控 merge commit 合并并 Push；
9. 合并后发送 `devflow_post_merge`。

不得在候选生成后直接使用 `git diff origin/main HEAD` 作为初始 Scope，因为移动的 `main` 会把自身独有提交误算为候选变化。

### 合并边界分类

- 缺少 Git `user.name` / `user.email` 属于执行器机械配置错误，必须由 Workflow 固定配置，不应通知用户；
- merge conflict、branch protection、权限拒绝或远端拒绝才属于真实 `AUTO_MERGE_BLOCKED`；
- Product Gate 不直接发送 merge-failure Issue，而是 Fail Closed，交给统一 Auto Recovery 根据失败步骤分类；
- 真实 merge boundary 只要求人工处理合并边界，不得再调用 Codex 修改产品代码。

## Post-Merge

Post-Merge 在 exact `main` 上运行指定 Profile。失败时仍按同一 Recovery Generation 预算处理；成功且 `notify_completion=true` 时：

- 自动更新 canonical state；
- 生成阶段结果和最终报告；
- 验证完成态；
- 提交收尾文档；
- 发送一次 `COMPLETED`；
- 关闭 canonical task-control Issue。

## 人工通知

只有自动恢复不再安全或不再有预算时才发送通知。通知中的 `/ack` 不会触发任何动作。用户完成外部配置、权限或业务决定后，使用 `/resume` 或回到 ChatGPT Web 提供新事实。


## Codex 调用前熔断

1. 若结构化结果是 `BLOCKED`，停止该 Generation；不重跑模型；
2. 若 State Consistency 缺少不可变 Task Descriptor 或真实失败路径不在允许范围，交由 ChatGPT Web 直接修复；
3. 不得从 `main` 合成固定五文件范围来猜测功能分支失败；
4. 修复恢复策略本身时先打开全局熔断，确定性 Gate 全部通过后再恢复模型入口。
