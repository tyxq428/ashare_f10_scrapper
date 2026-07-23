# W05-HF07 结果：Product Gate Git 提交身份与统一恢复分类

## 状态

```yaml
status: PASS
pull_request: 41
product_gate_run_id: 30001538021
product_merge_sha: 9e00e040474613eb0ec9cf5738cb3523900ea416
post_merge_run_id: 30001634301
```

## 根因

低风险候选已通过 Scope Guard 和 Full Gate，但 GitHub Runner 在创建 merge commit 前没有配置 `user.name` 与 `user.email`，因此出现 `Committer identity unknown`。旧 Product Gate 随即直接发送 `AUTO_MERGE_BLOCKED`，把机械执行器缺陷误报为人工门槛。

## 修复

- 在 rebase/merge 前固定：
  - `github-actions[bot]`
  - `41898282+github-actions[bot]@users.noreply.github.com`
- Product Gate 不再直接通知 merge failure；失败时 Fail Closed，并交给统一 Auto Recovery 分类；
- 只有真实 merge conflict、branch protection 或权限拒绝才进入 `HUMAN_REQUIRED`；
- Issue #32 中最后一条假人工门槛已追加状态更正。

## 验收

- PR #41 的 State Consistency、完整 Test 和 E2E 全部通过；
- 复用既有 v3 产品候选，没有重新调用 Codex；
- Product Gate Run `30001538021` 完整通过；
- 自动合并生成产品 Merge SHA `9e00e040474613eb0ec9cf5738cb3523900ea416`；
- exact-main Post-Merge Run `30001634301` 通过。
