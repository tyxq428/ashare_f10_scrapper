# Codex Entrypoint Hardening v1 — Master Plan

## W00｜基线与全路径清单

冻结 `main` 基线；建立机器可读 Entrypoint Manifest；扫描所有自动 Dispatch、Retry、Recovery、Environment 和官方 Action 引用；记录当前零调用状态。

## W01｜删除 Product Gate 自动模型恢复

Full Gate 失败改为 `PRODUCT_GATE_WEB_REPAIR_REQUIRED`；删除 Recovery Descriptor、Recovery 分支和 Bot Dispatch；静态 Validator 永久禁止恢复。

## W02｜Recovery Generation 永久归零

Schema v2 必须显式 `max_recovery_generations=0`；Schema v1 历史值只读但有效值强制为 0；删除生产 `recovery_task.py`，保留时改为 Web-only 重规划资料生成器。

## W03｜模型 Job 不可重跑边界

Auto Recovery 不再监听或重跑 Codex Task；定义 `PRE_MODEL / RESERVED / MODEL_STARTED / CONSUMED` 状态；一旦 Grant 被预占，GitHub Re-run 和重复 Dispatch 均不能再次启动模型。

## W04｜可信控制平面

未来控制代码、Policy、Gate、Scope 和 Secret Audit 必须来自精确 `main` SHA；任务分支仅提供 Descriptor 与允许的产品文件，不得自证 Policy 或 Eligibility。

## W05｜最小必要性与正向 Allowlist

未知 Reason Code 默认 ChatGPT Web。仅允许 `LOCAL_IMPLEMENTATION_DEFECT`、`LOCAL_TEST_GAP`、`BOUNDED_PURE_REFACTOR`，并要求 `web_resolution_assessment` 证明当前 Web 会话不适合完成且 Codex 有独特本地工具循环收益。

## W06｜真实零 Token 复现

受信任 Prepare Job 在精确 Source SHA 上运行 Gate、提取失败文件、计算指纹并验证 Artifact Digest；不再接受任务分支自报 `reproduction.json` 作为最终证据。

## W07｜一次性 Grant、Ledger 与 Activation

Grant 有效期不超过 60 分钟；绑定任务 SHA、Descriptor Digest、Source Run、失败指纹与 Allowed Files Hash；模型调用前原子预占。长期入口保持无模型，一次性 Activation PR 才能临时加入模型 Job，执行后自动删除。

## W08｜验证、合并与 exact-main 收尾

运行 Devflow State Consistency、Upgrade Compatibility、完整 Test、真实 688521 E2E；合并后 exact-main 再验证；生成阶段结果与最终报告；确认 Codex 调用为 0、Policy 仍为 disabled。

## 统一验收

```yaml
codex_calls_during_optimization: 0
automatic_codex_dispatch_paths: 0
product_gate_codex_recovery: false
post_merge_codex_recovery: false
auto_recovery_codex_retry: false
unknown_reason_codex_candidate: false
max_recovery_generations_effective: 0
trusted_control_ref_required: true
real_pre_model_reproduction_required: true
one_time_grant_required: true
grant_ttl_minutes_max: 60
model_job_rerunnable: false
policy_after_completion: disabled
```
