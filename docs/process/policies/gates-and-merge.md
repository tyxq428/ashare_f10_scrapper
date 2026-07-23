# Gate、自动合并与 Post-Merge 政策

## Gate 分层

| Gate | 用途 |
|---|---|
| G0 | 状态、文档、分支、范围、Secret 和 Workflow 静态安全 |
| G1 | 当前工作包的定向 Ruff、pytest 或 verifier |
| G2 | 仓库完整 `repository-full` 回归 |
| G3 | 真实但有限的模块/市场薄切片 |
| G4 | 产品级 E2E、多样本和性能矩阵 |
| G5 | exact-main 独立 Post-Merge |

## 执行边界

- Codex 只在单个 Task Generation 内运行 G1；G2–G5 全部在 Codex 会话之外执行。
- Gate 命令必须来自仓库拥有的受信 `gate_profile`，不得从任务文本、Issue 评论或 Workflow input 执行任意 Shell。
- Product Gate 必须重新验证 changed-path scope，不能只信任 Codex 结果。
- Secret-free Publish Job、Product Gate 和 Post-Merge 不得引用 `agent-runtime` Environment。
- 机械格式问题应由同版本工具修复并留下回归，不反复人工猜测。

## Product Gate 范围基线

候选产品分支创建后，`main` 可能继续出现文档、编排或其他不相关提交。初始 Product Gate不得使用双点：

```text
git diff origin/main HEAD
```

因为它会把 `main` 独有的后续提交也计算为候选差异，产生假 Scope Violation。正确顺序：

```text
1. 验证 expected_base_sha 是候选分支祖先；
2. 计算 merge_base = git merge-base origin/main HEAD；
3. 只校验 merge_base..HEAD 的新增路径；
4. Scope通过后执行 Full Gate；
5. 合并前若main已推进，rebase到最新main；
6. rebase后再以 origin/main..HEAD校验范围并重跑Full Gate。
```

Merge Base只解决移动主分支带来的差异口径，不会放宽任务起点和允许路径。真实 Scope失败必须 Fail Closed，产生只含路径的安全 Artifact，并由 Auto Recovery分类为 `SECURITY_BLOCKED`；不得用 Codex扩大范围绕过。

## 低风险自动合并

只有 Task Descriptor 同时满足以下条件，Actions 才可以自动合并：

```yaml
risk_class: low
auto_merge: true
allowed_files: 1-5 个明确路径
full_gate_profile: 受信任Profile
post_merge_profile: 受信任Profile
expected_base_sha: 40位main SHA
```

并且：

- 允许路径不得包含 `.github/**`、`docs/**`、`src/**`、Secrets 或数据迁移；
- 不涉及业务口径、来源优先级、Schema、权限和不可逆操作；
- Scope Guard、Secret Audit、G1 和 G2 全部 PASS；
- 当前 `main` 变化时，必须安全 rebase、重新执行 Scope Guard 和 G2；
- rebase/merge前必须设置仓库级身份：`github-actions[bot]` 与官方 noreply 邮箱，避免 Runner 临时环境缺少 committer identity；
- rebase 冲突、分支保护或权限阻断属于 `HUMAN_REQUIRED`，不能强推；
- merge步骤不得直接发送用户通知。它必须返回真实失败，由 `Devflow Auto Recovery`统一分类、去重和升级；
- 合并使用受控 merge commit，并记录产品 Merge SHA。

Git身份是确定性机械配置，不是人工门槛；冲突、分支保护与权限才是实际合并边界。

## 显式接力

`GITHUB_TOKEN` 写入后的普通 Push 不作为后续 Gate 的唯一触发条件。每个阶段通过 `repository_dispatch` 显式接力：

```text
Codex Publish
→ devflow_product_gate
→ low-risk auto merge
→ devflow_post_merge
→ final closeout
→ devflow_notify(COMPLETED)
```

## 失败与 Recovery Generation

- G1 失败：同一 Codex Run 可按 Auto Recovery 策略定向重跑失败 Job 一次。
- G2 或 G5 失败：若仍在批准路径内且 `recovery_generation < max_recovery_generations`，创建一个新的受限 Codex Recovery Generation。
- Recovery Generation 继承原允许路径、禁止路径、Gate、风险等级和自动合并授权，不能扩大范围。
- 预算内恢复静默执行。
- Recovery Generation 仍失败或 Scope/Security 门禁失败后，才进入 `INTERRUPTED` 或 `SECURITY_BLOCKED`。
- 低风险候选已通过全部Gate但无法安全合并时，Auto Recovery输出 `HUMAN_REQUIRED/AUTO_MERGE_BLOCKED`，不再调用Codex修代码。

## 完成条件

合并前全部 PASS 不等于完成。只有 exact-main G5、canonical state、阶段结果和最终报告全部通过后，任务才能标记 `DONE` 并发送一次完成通知。
