# Runbook：零模型自动恢复、自动继续与通知升级

## 输入

`Devflow Auto Recovery` 接收受管 Workflow 的终态，并读取：

- Workflow name、Run ID、Run attempt 和 conclusion；
- Job/Step 名称与 conclusion；
- 安全摘要 Artifact；
- 可用时的 immutable Task Descriptor；
- canonical infrastructure retry budget。

不读取或输出 Relay URL、Key、模型 ID、完整环境或原始 HTTP 日志。

## 分类结果

| Action | 系统动作 | 用户通知 |
|---|---|---|
| `NOOP` | 无动作 | 否 |
| `RETRY` | 仅重跑已验证的基础设施失败 Job | 否 |
| `HUMAN_REQUIRED` | 停止并给出唯一人工动作 | 是 |
| `SECURITY_BLOCKED` | 阻止发布和自动恢复 | 是 |
| `INTERRUPTED` | 路由 ChatGPT Web 或预算耗尽 | 是 |
| `COMPLETED` | 记录完成状态 | 是，最多 1 次 |

不存在 `RETRY_CODEX` 或自动 `CODEX_REPAIR` 路径。

## 唯一允许的自动重试

仅以下已验证的基础设施问题可在预算内调用 `rerun-failed-jobs`：

- Runner 启动、排队、取消、超时或 stale；
- Checkout、setup、依赖下载；
- Artifact 上传或下载；
- GitHub API 的明确临时错误；
- Relay Health 的传输检查，但不得因此启动模型。

重试只针对失败 Job，保留成功检查点；成功后静默继续。

## 必须交给 ChatGPT Web 的失败

以下失败不自动修复、不自动派发 Codex：

- State Consistency；
- Workflow 和 Devflow Core；
- Ruff、格式、Import、Fixture、路径和 Schema；
- Product Gate 的非基础设施失败；
- Post-Merge；
- Secret、Scope、Manifest 和权限；
- 业务语义、数据源冲突和架构决策；
- 任何模型返回的 `BLOCKED / NO_CHANGES / UNVERIFIED / FAILURE / TIMEOUT`。

处理顺序：

```text
读取确定性日志与Artifact
→ 识别真实失败文件
→ ChatGPT Web直接修改
→ 重跑最小Gate
→ 成功后继续
```

不得从 `main` 合成固定文件范围来猜测功能分支失败。

## Codex Candidate 只记录，不执行

若未来出现一个看似适合 Codex 的局部产品代码问题，自动恢复最多将其标记为候选；不得创建分支、写入 Descriptor、启动 Environment 或 Dispatch `codex-task.yml`。

后续必须由 ChatGPT Web：

1. 先复现失败；
2. 确认失败文件被 2–5 个安全文件覆盖；
3. 生成不可变 Descriptor 和失败指纹；
4. 获得用户明确授权；
5. 通过 Context、重复和用量门禁；
6. 通过独立 PR 恢复模型 Job；
7. 用户再次明确要求后才执行一次。

当前仓库 `mode: disabled`，因此候选也不会调用模型。

## Product Gate

Product Gate 继续执行 Scope、Full Gate、受控合并和 merge-boundary 分类，但失败处理如下：

- Scope violation → `SECURITY_BLOCKED`；
- 真实 merge conflict、Branch Protection 或权限拒绝 → `HUMAN_REQUIRED`；
- 代码或 Gate 失败 → `INTERRUPTED`，交给 ChatGPT Web；
- 不创建 Codex Recovery Generation；
- 不重跑失败 Codex Job。

## Post-Merge

Post-Merge 在 exact `main` 上运行指定 Profile：

- PASS：记录成功，继续 canonical closeout；
- FAIL：发送 `POST_MERGE_WEB_REPAIR_REQUIRED`，由 ChatGPT Web 直接修复或回滚；
- 不声明 `agent-runtime`；
- 不访问 Relay Secret；
- 不调用 `recovery_task.py`；
- 不 Dispatch Codex。

## 通知

只有以下状态才通知：

```text
COMPLETED
HUMAN_REQUIRED
SECURITY_BLOCKED
INTERRUPTED
```

基础设施重试、确定性修复和普通阶段 PASS 保持静默。`/ack` 仅确认收到，不触发修复、重试、恢复或模型调用。
