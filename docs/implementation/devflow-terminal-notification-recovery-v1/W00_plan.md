# W00 计划：完成事件生产失败面与恢复设计

## 输入

- closeout merge `5afbb17a574bb850e93d6134719b621e3fdfd10c`；
- `devflow-bark-delivery-receipt-v1` DONE state；
- 当前 `devflow-state-consistency.yml` 内嵌producer；
- `terminal_notification_scan.py`；
- `notification_event.py`；
- `devflow-incident.yml`；
- notification manifest、Validator和测试。

## 核验

1. canonical DONE是否完整；
2. canonical Issue是否产生；
3. 当前producer是否具备独立可观测Run；
4. producer失败是否可由Connector定位；
5. 如何在不重发旧事件的情况下恢复；
6. 如何跨generation保证每个task只完成通知一次。

## 设计原则

- State Consistency只负责验证；
- completion producer必须是独立可观察Workflow；
- producer只处理成功main push，不处理失败或PR；
- Incident仍不直接监听workflow_run；
- stable completion marker跨generation去重；
- producer/dispatch/notification失败均fail-open；
-不读取Bark Secret，不执行Bark POST。

## Gate

```yaml
canonical_done_valid: required
canonical_issue_absent: evidence_required
new_bark_requests: 0
secret_reads: 0
model_calls: 0
```