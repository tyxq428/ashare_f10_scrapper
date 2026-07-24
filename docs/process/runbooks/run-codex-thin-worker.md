# Runbook：一次性 Codex Thin Worker Activation

## 当前永久状态

仓库级 Policy 默认为 `disabled`。常驻 `.github/workflows/codex-task.yml` 只执行零 Token 候选复核，不包含：

- `agent-runtime`；
- Relay Secret；
- localhost Forwarder；
- `openai/codex-action`；
- Publish 或 Product Gate 接力。

只修改 `mode: enabled` 也不会启动模型。

## 唯一适用条件

所有条件必须同时成立：

1. Reason Code 为 `LOCAL_IMPLEMENTATION_DEFECT`、`LOCAL_TEST_GAP` 或 `BOUNDED_PURE_REFACTOR`；
2. ChatGPT Web 已分析该任务，并记录当前会话无法实际完成的独特原因；
3. 独特收益只能是 `LOCAL_ITERATIVE_TOOL_LOOP` 或用户明确要求独立后台 Worker；
4. 失败由受信任 Pre-model Job 在精确 Source SHA 上真实复现；
5. 失败文件全部落在 2–5 个普通产品代码/测试文件中；
6. 不含 Workflow、Devflow、文档、Secret、Schema、迁移、权限或业务语义；
7. Context Budget 通过；
8. 同一 Task、Failure Fingerprint 和 Grant 从未使用；
9. 用户针对该 Task SHA 再次明确授权一次调用。

任一条件不满足，继续由 ChatGPT Web 或确定性脚本处理。

## Phase A｜零 Token 候选复核

1. 从精确 `main` 创建 data-only `task/codex-*` 分支；
2. Descriptor 使用 schema v2、XHigh、`max_recovery_generations=0`；
3. 写入 `failure_context.reason_code` 和 `web_resolution_assessment`；
4. 手工 Dispatch 常驻 `Codex Task`，同时提供精确 Task Commit SHA；
5. Workflow 分别 Checkout：
   - `control/`：精确 `main`，提供 Policy 和复核代码；
   - `workspace/`：精确任务 SHA，只作为数据与产品工作区；
6. 任务分支中的 `.github/**`、`.devflow/**`、`scripts/devflow/**` 不执行；
7. 输出只表示候选是否值得提交 Activation PR，模型调用仍为 0。

## Phase B｜受信任 Pre-model 证据

一次性 Activation PR 必须先建立不接触 Secret 的 Prepare Job：

1. Checkout 精确控制 SHA、任务 SHA 和 Source SHA；
2. 从控制平面读取 Gate Profile；
3. 真实运行 Gate；
4. Gate 必须稳定失败；已 PASS 时返回 `FAILURE_NOT_REPRODUCIBLE`；
5. 从受信任输出提取失败文件和 Fingerprint；
6. 验证 Source Run、Source SHA 与 Artifact Digest；
7. 生成 `trusted_pre_model_job` 证据；
8. 验证失败文件完全被 Allowed Files 覆盖。

任务分支自报的 `reproduction.json` 不能替代该证据。

## Phase C｜一次性 Grant

Grant 必须绑定：

```yaml
grant_id:
task_id:
task_commit_sha:
descriptor_sha256:
source_run_id:
source_commit_sha:
failure_fingerprint:
allowed_files_hash:
approved_by: tyxq428
approval_source: chatgpt_web
max_calls: 1
state: ISSUED
issued_at_utc:
expires_at_utc:  # 最长60分钟
```

模型 Job 前，在按 `grant_id` 序列化的 Workflow 中将 Ledger 原子写为 `RESERVED`。一旦预占，成功、失败、取消、超时或 Artifact 错误均不得再次启动模型；结束时写为 `CONSUMED`。

## Phase D｜一次性 Activation PR

- Activation PR 只绑定一个 Grant、Task SHA 和 Descriptor Digest；
- Secret-bearing Job 从精确控制 SHA加载执行代码；
- 任务工作区代码不提供 Policy、Eligibility、Gate 或 Secret Audit 实现；
- 模型 Job：`contents: read`、`persist-credentials: false`、一次 XHigh Session；
- 模型 Job 不受 `rerun-failed-jobs` 管理；
- Model 开始后任何失败都消耗 Grant；
- Patch 只从 Allowed Files 生成并冻结 Hash；
- Gate 输出写到 `/tmp`，不得污染 Patch；
- Secret-free Job 重新验证 Patch、Scope、Manifest 和 Gate；
- Activation 执行后删除模型 Job并恢复 `disabled`。

## 禁止路径

- Product Gate、Post-Merge、State Consistency 或 Auto Recovery 创建 Recovery Generation；
- `github-actions[bot]` 派发模型；
- GitHub UI Re-run 重复模型；
- 未知 Reason Code 因文件数恰好为 2–5 而进入候选；
- 用降低推理强度代替缩小 Context；
- 同一 Descriptor、Task、Fingerprint 或 Grant 第二次调用。
