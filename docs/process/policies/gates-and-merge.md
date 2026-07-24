# Gate、合并与零模型失败处理政策

## Gate 分层

| Gate | 用途 |
|---|---|
| G0 | 状态、文档、分支、Context、Scope、Secret、Entrypoint 和 Workflow 静态安全 |
| G1 | 当前工作包的定向 Ruff、pytest 或 verifier |
| G2 | 仓库完整 `repository-full` 回归 |
| G3 | 真实但有限的模块/市场薄切片 |
| G4 | 产品级 E2E、多样本和性能矩阵 |
| G5 | exact-main 独立 Post-Merge |

## 影响感知选择

```text
docs_only
→ 文档链接、State/Template格式

devflow_only
→ G0 + Devflow compile/Ruff/pytest + Upgrade Compatibility

product
→ G0 + G2 + 真实E2E + exact-main关键回归
```

未知路径和混合改动按最高风险处理；手工派发只能增加 Gate，不能降低 Gate。依赖缓存只缓存依赖，不缓存 Scope、Secret、Diff、Gate 或 Post-Merge 结论。

## Codex 边界

- 常驻 Workflow 不运行模型；
- 未来一次性 Activation 只允许模型执行 G1；
- G2–G5 永远在模型会话之外执行；
- 模型前必须有受信任真实复现、一次性 Grant 和 Context PASS；
- Model-bearing Job 不可自动重跑；
- `max_recovery_generations` 的有效值永久为 0。

## Product Gate

1. 验证 `expected_base_sha` 是候选祖先；
2. 计算 `merge_base = git merge-base origin/main HEAD`；
3. 只校验 `merge_base..HEAD`；
4. Scope 通过后执行 Full Gate；
5. `main` 推进时安全 rebase，并重跑 Scope 与 Full Gate；
6. Full Gate 失败时输出 `PRODUCT_GATE_WEB_REPAIR_REQUIRED`，交给 ChatGPT Web；
7. Product Gate 不创建 Recovery Descriptor、Recovery 分支或 Codex Dispatch；
8. Scope Violation 为 `SECURITY_BLOCKED`；
9. Merge conflict、Branch Protection 或权限拒绝为 `HUMAN_REQUIRED`。

## 低风险自动合并

只有已存在且通过全部 Gate 的受审候选可以自动合并，并且：

- `risk_class=low`；
- `auto_merge=true`；
- 最多 5 个明确安全路径；
- 不含 `.github/**`、`docs/**`、`src/**`、Secret、Schema 或迁移；
- Context、Scope、Secret、G1、G2 全部 PASS；
- rebase 后重新验收；
- 使用受控 merge commit；
- 冲突或权限阻断不得强推。

## Post-Merge

Exact-main G5 失败时：

```text
POST_MERGE_WEB_REPAIR_REQUIRED
→ ChatGPT Web读取确定性证据
→ 直接修复或回滚
→ 不创建Codex Recovery
```

## 失败分类

| 失败 | 处理 |
|---|---|
| Ruff / Format / Import / Fixture | 确定性修复 |
| Runner / Checkout / 依赖 / Artifact（模型前） | 有限重跑失败 Job |
| State / Workflow / Devflow | ChatGPT Web |
| Product Full Gate | ChatGPT Web |
| Post-Merge | ChatGPT Web / 回滚 |
| Scope / Secret / Manifest | Security Blocked |
| Merge Boundary | Human Required |
| 已开始的模型 Job 失败、超时或取消 | Grant 消耗，禁止重跑 |

## 完成条件

合并前 PASS 不等于完成。只有 exact-main G5、Canonical State、阶段结果、升级兼容、Entrypoint 扫描和最终报告全部通过后，任务才能标记 `DONE`。
