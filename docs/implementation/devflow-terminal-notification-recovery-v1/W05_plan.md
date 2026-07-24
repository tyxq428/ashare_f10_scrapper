# W05 计划：实现合并、原子Closeout与真实Bark验证

## 实现合并前

1. canonical state保持 `VERIFYING / RUNNING / W05`；
2. notification generation仍为0；
3. 对最终精确PR head再次运行：
   - Upgrade Compatibility；
   - Test；
   - State Consistency；
   - 真实E2E 688521；
4. 确认唯一开放PR和并行路径交集0；
5. PR #58转Ready并合并。

## Exact-main核验

-记录implementation merge SHA；
-确认merge tree相对测试head无文件差异；
-确认Codex Policy disabled；
-确认State Consistency只做验证；
-确认独立producer存在且scanner唯一；
-确认Incident stable marker、Bark和receipt边界不变。

## 原子Closeout

从implementation merge SHA创建独立closeout PR，一次性更新：

- `task_state.yaml` → `DONE / COMPLETED / PASS`；
- `ACTIVE_TASKS.yaml` → `DONE / main`；
- `STATUS.md`；
- `HANDOFF.md`；
- `W05_result.md`；
- `FINAL_REPORT.md`。

Closeout notification：

```yaml
generation: 1
last_type: COMPLETED
acknowledged: false
```

## 真实验证链

```text
closeout main push
→ Devflow State Consistency PASS
→ Devflow Terminal State Notification
→ devflow_notify
→ canonical Issue stable marker
→ Devflow Incident
→ at most one Bark POST
→ bark-delivery-result.json
→ single-file Artifact
→ [BARK][DELIVERY_RECEIPT] index
```

验证：

1. 找到新任务control Issue；
2. 确认COMPLETED和stable marker各一次；
3. 记录producer Run和Incident Run；
4.读取回执索引的Artifact ID；
5.下载ZIP并确认单一JSON；
6.运行 `bark_delivery_result.py validate`；
7.记录 `request_initiated`、attempt count、curl exit和HTTP status；
8.使用纯文档观察PR追加实际结果，不修改task state/generation。

## 失败语义

- producer/dispatch/Bark/receipt/upload/index失败均不撤销DONE；
-不UI Re-run补发；
-不创建synthetic测试；
-stable marker阻止任何恢复generation重复Bark；
-只有有效回执提供正向Transport证据。

## 最终预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_requests_before_closeout: 0
bark_requests_for_closeout_max: 1
bark_automatic_retries: 0
bark_secret_value_reads_by_chatgpt: 0
```