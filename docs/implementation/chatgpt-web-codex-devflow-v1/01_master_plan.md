# 主计划：chatgpt-web-codex-devflow-v1

## 目标架构

```text
ChatGPT Web Supervisor
→ canonical task state + Wxx plans/results
→ GitHub Actions deterministic executor
→ Codex Thin Worker (one task / one session / low effort)
→ secret-free patch publication
→ Web PR review and merge
→ independent post-merge verification
```

## 工作包

| 阶段 | 目标 | Gate | 自动继续 | 人工门槛 |
|---|---|---|---|---|
| W00 | 基线、合同、安全预检 | G0 | 是 | 正式 Secret/权限缺失 |
| W01 | 分层 SOP 与 AGENTS | G0/G1 | 是 | 指令冲突 |
| W02 | Canonical state 与一致性引擎 | G0/G1 | 是 | 状态迁移歧义 |
| W03 | Gate、Scope Guard、Failure Bundle | G1 | 是 | 不可安全映射命令 |
| W04 | Reusable Codex、Relay、Audit、Incident、post-merge | G0/G1/G2 | 是 | 安全测试失败 |
| W05 | PR-A 合并和独立 post-merge | G2/G5 | 是 | 合并冲突/回归失败 |
| W06 | 真实低风险 Codex 薄切片 | G0/G1/G2/G5 | 是 | Codex越界/语义决策 |
| W07 | 后续三个低风险任务渐进迁移标准 | 指标 Gate | 是 | 失败率超限 |
| W08 | 收尾、清理、经验和最终报告 | G5 | 是 | 未解决必做项 |

## 真实薄切片

修复 `scripts/run_resilient_command.py`：最后一次可重试失败已经耗尽 `max_attempts` 时，整体报告必须是 `FAILED`，不能残留 `RETRYING`。只允许修改该脚本和 `tests/test_resilient_fetch.py`。

## 预算

- 正式 Codex Session：1；
- 自动第二 Session：0；
- Codex effort：low；
- 基础设施重试：最多 3，且只重试失败部分；
- 总输入观察阈值：100K；输出观察阈值：2K。

## 合并策略

PR-A 只交付执行基础设施；合并并 post-merge 通过后，才通过独立 PR-B 执行真实薄切片。两个 PR 均由 ChatGPT Web 审查并在 Gate 通过后合并。
