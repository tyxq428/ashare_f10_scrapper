# Devflow Bark Terminal Notification v1 最终报告

## 1. 最终结论

仓库现已具备任务级终态手机提醒能力。通知对象不是任意 Workflow 结束，而是经过 canonical state 与确定性恢复边界确认后的四种有价值终态：

```text
COMPLETED
INTERRUPTED
HUMAN_REQUIRED
SECURITY_BLOCKED
```

通知通过统一 `repository_dispatch: devflow_notify` 总线进入 `Devflow Incident`，先写入 canonical task-control Issue marker，再尝试最多一次 Bark HTTP POST。

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
implementation_pull_request: 54
implementation_merge_sha: 4d782d8328b2e106708855d643e8e367c0cff73d
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_automatic_retries: 0
human_action_remaining: false
```

## 2. 通知架构

```text
Workflow / Gate failure
→ Devflow Auto Recovery分类和有限基础设施重试
→ 真实终态决定
→ repository_dispatch: devflow_notify
→ Devflow Incident
   ├─ canonical task-control Issue
   └─ notification-runtime / Bark
```

成功路径：

```text
canonical state更新为DONE
→ Devflow State Consistency全部通过
→ 扫描新的COMPLETED generation
→ devflow_notify
→ Issue marker
→ Bark
```

普通测试、E2E、阶段完成、缓存命中、重试和确定性修复继续静默。

## 3. Canonical事件合同

所有事件必须绑定一个登记在 `ACTIVE_TASKS.yaml` 的精确 `task_id`，并提供：

- `notification_type`；
- `reason_code`；
- 裁剪后的原因与最小动作；
- 稳定 fingerprint；
- 来源 Workflow 和 Run ID；
- 最多20个失败 Step；
- 当前仓库内的安全目标URL。

`COMPLETED` 额外要求：

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
post_merge: PASS
human_gate.required: false
notification.last_type: COMPLETED
notification.acknowledged: false
notification.generation: positive_and_exactly_bound
```

伪造generation、错误来源、已ack事件、晚到的中断事件和仓库外target URL全部Fail Closed。

## 4. 去重和投递语义

逻辑去重键：

```text
task_id + fingerprint + notification_type
```

Incident先将marker持久化到canonical Issue，再允许Bark Job运行。因此：

```yaml
delivery_semantics: at_most_once
github_rerun_resend: false
run_attempt_must_equal: 1
automatic_retry: false
maximum_requests_per_notification: 1
```

GitHub UI Re-run、重复repository_dispatch或同一根因的多个Workflow失败不会重复发送Bark。

## 5. Bark安全边界

Bark使用独立Environment：

```yaml
environment: notification-runtime
required_reviewers: none
administrator_bypass: disabled
deployment_branches:
  - main
secret: BARK_PUSH_URL
```

该Environment与模型/Relay使用的 `agent-runtime` 完全分离。只有 `.github/workflows/devflow-incident.yml` 可以引用 `notification-runtime` 和 `BARK_PUSH_URL`。

Transport约束：

- HTTPS only；
- TLS 1.2 minimum；
- `curl --retry 0`；
- 最多一个POST位置；
- 不输出Endpoint诊断；
- 不保存或上传响应正文；
- Bark失败 `continue-on-error`；
- 不触发Auto Recovery；
- 不改变canonical state或任务结论。

## 6. Canonical Issue

每个任务使用精确标题：

```text
[TASK CONTROL] <task-id>
```

优先使用canonical state中的 `control_issue_number`。若尚未持久化编号，只能按精确标题寻找非PR Issue；没有匹配时创建，多个匹配时Fail Closed。

Issue记录是权威的持久通知；Bark只是即时提醒。`/ack` 只表示已看到，不会触发修复、重跑、Codex、恢复或状态修改。

## 7. 失败生产者收敛

- Product Gate失败不再直接重复发送 `devflow_notify`；
- Post Merge失败不再直接重复发送 `devflow_notify`；
- 两者统一由 Auto Recovery进行确定性分类；
- Auto Recovery在发送终态事件前绑定唯一canonical非DONE任务；
- Auto Recovery不监听Incident或Bark，不重试Bark；
- Relay Health和Codex Task不在该通知重试链中。

## 8. 完成生产者

完成事件由 `Devflow State Consistency` 的后置Job产生，必须满足：

- 事件为push；
- 分支为main；
- consistency Job成功；
- 精确checkout `github.sha`；
- canonical state出现新的未ack `COMPLETED` generation；
- 完成事件本身不读取Bark Secret；
- 扫描或dispatch失败为fail-open，不使State Consistency红灯，也不触发Auto Recovery。

## 9. 确定性Gate

最终实现head：

```text
e5a3678057640a426a941f609bbe0f14eace1011
```

| Gate | Run ID | 结果 |
|---|---:|---|
| Devflow Upgrade Compatibility | `30090241713` | PASS |
| Test | `30090241743` | PASS |
| Devflow State Consistency | `30090241736` | PASS |
| E2E 688521 | `30090241816` | PASS |

PR #54合并SHA：

```text
4d782d8328b2e106708855d643e8e367c0cff73d
```

该Merge SHA相对精确测试head只有一个merge commit，文件差异为0。Merge SHA上的Codex Policy仍为disabled，通知清单仍要求单次、无重试、fail-open Bark和State Consistency完成门禁。

当前连接器不能按Merge SHA列举push事件的全部Actions Run ID，本报告不虚构相关编号；exact-main源码结论由无文件差异、精确Merge SHA读取和最终canonical State Consistency组成。

## 10. 平台配置

用户已通过GitHub UI确认：

```yaml
notification-runtime:
  required_reviewers: none
  administrator_bypass: disabled
  deployment_branches:
    - main
  BARK_PUSH_URL:
    configured: true
    value_shared_or_read: false
```

Secret值未进入聊天、仓库、PR、Issue、日志或Artifact。

## 11. 真实端到端验证

没有增加synthetic Bark测试Workflow。本任务最终closeout进入main后，其新的canonical DONE generation即为一次真实业务完成事件：

```text
DONE generation
→ State Consistency PASS
→ devflow_notify
→ canonical Issue marker
→ one Bark POST at most
```

Bark返回HTTP 2xx时代表服务端接受；连接或HTTP失败时记录fail-open。两种结果都不撤销已经成立的DONE事实。实际投递观察可在closeout合并后补充到本报告，但不会再次修改task_state generation或重复发送Bark。

## 12. 最终安全与成本计数

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
raw_workflow_run_direct_notifications: 0
synthetic_bark_tests: 0
bark_automatic_retries: 0
bark_requests_before_final_completion_event: 0
bark_requests_for_final_completion_event_max: 1
```
