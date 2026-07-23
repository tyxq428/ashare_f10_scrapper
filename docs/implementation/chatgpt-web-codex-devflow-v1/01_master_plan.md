# 主计划：chatgpt-web-codex-devflow-v1

## 目标架构

```text
ChatGPT Web Supervisor
→ canonical task state + Wxx plans/results
→ GitHub Actions deterministic executor
→ failure classifier + bounded auto recovery
→ Codex Thin Worker (one task generation / one session / low effort)
→ secret-free patch publication
→ full Product Gate
→ explicit low-risk automatic merge
→ independent exact-main post-merge verification
→ one final completion notification
```

## 工作包

| 阶段 | 目标 | Gate | 自动继续 | 人工门槛 |
|---|---|---|---|---|
| W00 | 基线、合同、安全预检 | G0 | 是 | 正式 Secret/权限缺失 |
| W01 | 分层 SOP 与 AGENTS | G0/G1 | 是 | 指令冲突 |
| W02 | Canonical state 与一致性引擎 | G0/G1 | 是 | 状态迁移歧义 |
| W03 | Gate、Scope Guard、Failure Bundle | G1 | 是 | 不可安全映射命令 |
| W04 | Reusable Codex、Relay、Audit、Incident、post-merge | G0/G1/G2 | 是 | 安全测试失败 |
| W05 | PR-A、post-merge 与 Auto Recovery Controller | G2/G5 | 是 | 安全/权限/预算耗尽 |
| W06 | 真实低风险 Codex 无人值守薄切片 | G0/G1/G2/G5 | 是 | Codex越界/语义决策 |
| W07 | 后续三个低风险任务渐进迁移标准 | 指标 Gate | 是 | 失败率超限 |
| W08 | 自动收尾、经验和最终报告 | G5 | 是 | 未解决必做项 |

## 真实薄切片

修复 `scripts/run_resilient_command.py`：最后一次可重试失败已经耗尽 `max_attempts` 时，整体报告必须是 `FAILED`，不能残留 `RETRYING`。只允许修改该脚本和 `tests/test_resilient_fetch.py`。

## 自动恢复预算

- 基础设施失败：最多 3 次失败 Job 定向重跑；
- 每个 Task Generation：1 个 Codex Session；
- 自动第二 Session：0；
- Full/Post-Merge Gate：最多创建 1 个受限 Codex Recovery Generation；
- Codex effort：low；
- 同一 Root Cause 超出预算后才通知用户。

## 通知策略

以下情况保持静默：阶段开始/完成、中间 PASS、自动重试、Codex recovery generation、分支 Push 和 Product Gate 成功。

只通知：

```text
[TASK][COMPLETED]
[TASK][HUMAN_REQUIRED]
[TASK][SECURITY_BLOCKED]
[TASK][INTERRUPTED]  # 仅自动恢复预算耗尽或无法安全分类
```

`/ack` 仅确认已看到，不触发修复、重试或继续。

## 合并策略

- Workflow、Secret、业务 Schema、数据来源和研究口径变更仍由 ChatGPT Web 审查；
- 只有任务描述显式设置 `risk_class=low`、`auto_merge=true`，允许文件不超过 5 个且全部 Gate 通过时，Actions 才可自动合并；
- 每次自动合并都通过 `repository_dispatch` 显式进入 exact-main Post-Merge，不能依赖 `GITHUB_TOKEN` Push 的隐式触发；
- Post-Merge 全部通过后，自动更新 canonical state、生成最终报告并只发送一次完成通知。
