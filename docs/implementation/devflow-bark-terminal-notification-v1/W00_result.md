# W00 结果：终态事件合同与现状库存

```yaml
status: PASS
allowed_terminal_types:
  - COMPLETED
  - INTERRUPTED
  - HUMAN_REQUIRED
  - SECURITY_BLOCKED
raw_workflow_run_direct_notifications: 0
existing_issue_deduplication: present
existing_bark_transport: absent
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
bark_requests: 0
```

## 当前实现库存

| 路径 | 当前行为 | 差异 |
|---|---|---|
| Notification Policy | 只允许四类有价值通知；中间状态静默 | 可直接复用 |
| `Devflow Incident` | 只监听 `repository_dispatch: devflow_notify`，通过 Issue marker去重 | task ID和 Issue均硬编码为旧任务；没有 Bark |
| Auto Recovery | 原始失败先分类、有限重试，终态才 dispatch | 终态 payload没有 task ID；成功路径不运行，`POST_MERGE_PASS`完成分类不可达 |
| Product Gate | Full Gate失败和未授权自动合并可直接 dispatch | payload缺少 task ID；失败路径可能与 Auto Recovery重复通知 |
| Post Merge | exact-main失败可直接 dispatch；成功只写 Summary | payload缺少 task ID；成功后没有完成通知 |
| `finalize_task.py` | 持久化 DONE、`notification.last_type=COMPLETED`、generation递增 | 不产生 `devflow_notify` |
| Workflow Validator | 禁止 Incident直接监听 raw `workflow_run` | 尚未约束 Bark Secret、唯一请求位置、无重试和独立 Environment |

## 关键结论

1. **不得监听所有 Workflow结束。** 现有架构已经正确区分原始 Workflow conclusion与任务终态。
2. **完成通知应来自 canonical state变更。** 当 `task_state.yaml` 在 main上首次进入严格 DONE条件且 notification generation递增时，才产生 `COMPLETED`。
3. **中断通知继续由 Recovery Policy产生。** 对无法从来源 payload读取 task ID的失败，只在 ACTIVE_TASKS中恰有一个非 DONE任务时安全解析；否则 Fail Closed。
4. **删除重复的失败自通知。** Product Gate和 Post Merge失败统一交给 Auto Recovery分类；未授权自动合并仍是成功路径中的显式 `HUMAN_REQUIRED`。
5. **Issue marker是逻辑去重源。** Incident先解析/创建精确 task-control Issue并写 marker，随后 Bark Job才可运行。
6. **Bark采用 at-most-once。** 仅 `github.run_attempt == 1`，每条逻辑通知一次 HTTP POST，无自动重试；失败不改变任务状态。
7. **Secret独立。** `BARK_PUSH_URL`只属于 `notification-runtime`，与 `agent-runtime`完全隔离。

## 固化事件字段

```yaml
required:
  - task_id
  - action
  - notification_type
  - reason_code
  - reason
  - minimum_action
  - fingerprint
  - source_workflow
  - source_run_id
optional:
  - failure_steps
  - target_url
```

`COMPLETED` 额外要求 canonical state满足：

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
post_merge: PASS
human_gate.required: false
notification.last_type: COMPLETED
```

## W01范围

- 新增通用事件校验与 Bark JSON渲染脚本；
- 新增 canonical state完成转换扫描脚本；
- 新增 notification channel机器清单；
- 增加纯单元测试，不发送真实网络请求。