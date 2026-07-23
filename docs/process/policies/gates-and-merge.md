# Gate、自动合并与 Post-Merge 政策

## Gate 分层

| Gate | 用途 |
|---|---|
| G0 | 状态、文档、分支、Context、Scope、Secret 和 Workflow 静态安全 |
| G1 | 当前工作包的定向 Ruff、pytest 或 verifier |
| G2 | 仓库完整 `repository-full` 回归 |
| G3 | 真实但有限的模块/市场薄切片 |
| G4 | 产品级 E2E、多样本和性能矩阵 |
| G5 | exact-main 独立 Post-Merge |

## 影响感知选择

`Test`、`E2E 688521` 和 Devflow Infrastructure Post-Merge 根据当前 diff 选择最小充分 Gate：

```text
docs_only
→ 文档链接、State/Template格式

devflow_only
→ G0 + Devflow compile/Ruff/pytest + Upgrade Compatibility

product
→ G0 + G2 + 真实E2E + exact-main关键回归
```

未知路径和混合改动按最高风险处理；手工派发只能强制增加 Gate，不能降低 Gate。稳定 Check 必须存在并明确记录跳过原因。

## 执行边界

- Codex 只运行 G1；G2–G5 在 Codex 会话之外执行；
- 模型调用前 Context Budget 必须 PASS；
- Gate 命令只能来自仓库拥有的受信 `gate_profile`；
- Product Gate 重新验证 changed-path scope；
- Secret-free Publish、Product Gate、Branch GC 和 Post-Merge 不引用 `agent-runtime`；
- 机械格式问题由同版本工具修复并留下回归。

## Product Gate 范围基线

异步候选不得直接使用：

```text
git diff origin/main HEAD
```

正确顺序：

1. 验证 `expected_base_sha` 是候选祖先；
2. 计算 `merge_base = git merge-base origin/main HEAD`；
3. 只校验 `merge_base..HEAD`；
4. Scope 通过后执行 Full Gate；
5. 合并前若 `main` 推进，安全 rebase；
6. rebase 后以最新 `origin/main..HEAD` 重跑 Scope 和 Full Gate。

Merge Base 不会放宽允许路径。真实 Scope 失败 Fail Closed，上传路径摘要并进入 `SECURITY_BLOCKED`。

## 低风险自动合并

Task Descriptor 必须满足：

```yaml
schema_version: 2
reasoning_effort: xhigh
context_budget: explicit
risk_class: low
auto_merge: true
allowed_files: 1-5 个明确安全路径
expected_base_sha: 40位SHA
```

并且：

- 不含 `.github/**`、`docs/**`、`src/**`、Secrets、Schema 或迁移；
- 不涉及业务口径、来源优先级、权限和不可逆操作；
- Context、Scope、Secret、G1 和 G2 全部 PASS；
- `main` 变化时 rebase 后重新验收；
- rebase/merge 前设置 `github-actions[bot]` Git 身份；
- 冲突、分支保护或权限阻断为真实 `HUMAN_REQUIRED`，不能强推；
- merge 失败交给统一 Auto Recovery 分类，不直接通知；
- 使用受控 merge commit 并记录产品 Merge SHA。

## 显式接力

不依赖 `GITHUB_TOKEN` Push 的递归触发：

```text
Codex Publish
→ devflow_product_gate
→ low-risk auto merge
→ devflow_post_merge
→ final closeout / completed notification
→ devflow_branch_gc(execute=false)
```

Branch GC 第一个生产阶段只生成 dry-run 计划；实际删除必须由独立政策显式启用。

## 失败与 Recovery Generation

- Context 失败：模型不启动，要求缩小或拆分任务，不能降低推理强度；
- G1 失败：同一 Codex Run 最多定向重跑失败 Job 一次；
- G2/G5 失败：预算内创建一个 schema-v2 XHigh Recovery Generation；
- Recovery 继承范围、Context、Gate、风险和自动合并授权；
- 预算内恢复静默；
- Scope/Secret 失败分别进入安全阻断；
- 合并边界失败不再调用 Codex 修代码。

## 完成条件

合并前 PASS 不等于完成。只有 exact-main G5、Canonical State、阶段结果、升级兼容和最终报告全部通过后，任务才能标记 `DONE`。依赖缓存、旧测试结果或跳过的中间步骤不能替代这些结论。
