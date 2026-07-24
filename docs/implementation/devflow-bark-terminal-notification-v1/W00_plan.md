# W00 计划：终态事件合同与现状库存

## 输入

- `docs/process/policies/notification-policy.md`；
- `.github/workflows/devflow-incident.yml`；
- `.github/workflows/devflow-auto-recovery.yml`；
- `.github/workflows/devflow-product-gate.yml`；
- `.github/workflows/devflow-post-merge.yml`；
- `scripts/devflow/recovery_policy.py`；
- `scripts/devflow/finalize_task.py`；
- `scripts/devflow/validate_workflows.py`；
- canonical task state与 `ACTIVE_TASKS.yaml`。

## 检查项

1. 哪些路径已经产生 `COMPLETED / INTERRUPTED / HUMAN_REQUIRED / SECURITY_BLOCKED`；
2. 哪些 payload缺少 `task_id`或依赖硬编码 task；
3. 完成通知是否在 canonical DONE之前产生；
4. 原始 Workflow failure是否会绕过自动恢复直接通知；
5. Issue去重能否扩展到 Bark；
6. GitHub UI Re-run是否可能重复推送；
7. Bark Secret应放置在哪个独立 Environment；
8. Bark失败是否可能污染任务终态或形成恢复循环。

## Gate

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
bark_requests: 0
inventory_complete: true
raw_workflow_run_notifications: 0
```

## 输出

- `W00_result.md`；
- 固化的事件字段和终态判定；
- W01实施范围。