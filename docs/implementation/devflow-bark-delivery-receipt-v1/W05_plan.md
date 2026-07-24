# W05 计划：实现合并、原子Closeout与真实Bark回执验证

## 阶段入口

W00–W04实现与确定性Gate已完成。W05只处理：

- 最终精确PR head验证；
- PR #56实现合并；
- exact-main源码核验；
- 原子DONE closeout；
- 本任务自身的单次真实Bark通知；
- 回执Artifact下载与离线校验。

## 实现合并前

1. canonical state保持：

```yaml
status: VERIFYING
execution_status: RUNNING
current_stage: W05
last_completed_stage: W04
notification:
  generation: 0
  last_type: null
  acknowledged: true
```

2. 对恢复后的最终精确PR head再次运行：
   - Upgrade Compatibility；
   - Test；
   - State Consistency；
   - 真实E2E 688521；
3. 所有Gate PASS后将PR #56转为Ready并合并；
4. 合并前再次确认没有并行开放PR路径交集。

## 实现合并后

1. 记录implementation merge SHA；
2. 核验main上：
   - Codex Policy仍为disabled；
   - Bark POST位置=1；
   - receipt Artifact上传位置=1；
   - receipt retention=14天；
   - Auto Recovery不监听Incident；
3. 从implementation merge SHA创建独立closeout分支；
4. 原子写入：
   - `W05_result.md`；
   - `FINAL_REPORT.md`；
   - `task_state.yaml` → `DONE / COMPLETED / PASS`；
   - `STATUS.md`；
   - `HANDOFF.md`；
   - `ACTIVE_TASKS.yaml` → `DONE / main`。

## Closeout状态

```yaml
status: DONE
execution_status: COMPLETED
acceptance: PASS
security_status: PASS
current_stage: W05
last_completed_stage: W05
post_merge: PASS
notification:
  generation: 1
  last_type: COMPLETED
  acknowledged: false
```

该原子push不会直接访问Bark Secret。必须先通过main的State Consistency，随后才产生 `devflow_notify`。

## 真实Bark验证

唯一live测试链：

```text
canonical DONE generation 1
→ main State Consistency PASS
→ devflow_notify
→ canonical Issue marker
→ at most one Bark POST
→ bark-delivery-result.json
→ receipt Artifact upload
→ [BARK][DELIVERY_RECEIPT] Issue index
```

验证步骤：

1. 找到 `[TASK CONTROL] devflow-bark-delivery-receipt-v1`；
2. 确认 `[TASK][COMPLETED]` marker只出现一次；
3. 读取 `[BARK][DELIVERY_RECEIPT]` 安全索引；
4. 记录Incident Run ID、Artifact ID和投递状态；
5. 下载Artifact ZIP；
6.确认ZIP只含一个 `bark-delivery-result.json`；
7. 运行：

```bash
python scripts/devflow/bark_delivery_result.py validate \
  --input bark-delivery-result.json
```

8. 判断：
   - `DELIVERED`：请求已发起1次且服务端HTTP 2xx；
   - `FAILED`：请求已发起1次但Transport失败；
   - `SKIPPED_MISSING_CONFIGURATION`：未发起请求。

## 观察后记录

Closeout产生DONE之后，不得修改notification generation或重发Bark。若需要把实际Artifact结果持久化到最终报告，使用一个纯文档观察PR，只更新 `W05_result.md` 和 `FINAL_REPORT.md`，不修改task_state或ACTIVE_TASKS。

## 失败语义

- Bark失败不撤销DONE；
- receipt生成、上传或Issue索引失败不撤销DONE；
- 不通过UI Re-run补发；
- 不创建synthetic测试Workflow；
- Artifact缺失不能证明请求未发起；
- 只有有效回执可证明request initiated和HTTP状态。

## 最终预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_live_requests_before_closeout: 0
bark_live_requests_for_closeout_max: 1
bark_automatic_retries: 0
bark_secret_value_reads_by_chatgpt: 0
```