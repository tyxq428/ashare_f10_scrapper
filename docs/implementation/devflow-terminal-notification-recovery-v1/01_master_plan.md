# 总计划：Devflow Terminal Notification Recovery v1

## W00｜失败面确认与生产者设计

- 确认上一closeout已DONE但未出现canonical Issue；
- 对账当前内嵌producer、Incident、scanner和validator；
- 设计独立 `workflow_run` success producer；
- 固化single-producer与stable completion marker语义。

## W01｜独立成功后继Producer

- 新增 `.github/workflows/devflow-terminal-state-notify.yml`；
- 监听 `Devflow State Consistency` 的 `workflow_run: completed`；
- 仅处理source event=push、head branch=main、conclusion=success；
- checkout source `head_sha`，验证其属于main历史；
- 使用第一父提交作为before SHA；
- 调用现有scanner并dispatch `devflow_notify`；
- production/dispatch失败全部fail-open；
- 从State Consistency移除内嵌通知Job。

## W02｜跨Generation完成去重

- `notification_event.py` 为COMPLETED生成稳定marker：`devflow-task-completed:<task-id>`；
- Incident在写评论和Bark前同时检查generation marker与稳定marker；
- COMPLETED评论写入两种marker；
-非完成通知继续只使用root-cause marker；
-并发仍按task ID序列化。

## W03｜清单、Validator、测试与文档

- notification manifest指向独立producer；
- Validator证明producer唯一、source筛选、精确SHA、fail-open、零Secret、零Bark；
- State Consistency不再包含dispatch逻辑；
- Auto Recovery不监听producer/Incident；
-新增scanner/marker/workflow测试；
-更新通知Policy和Incident Runbook。

## W04｜精确Head Gate与实现合并

-最终PR head运行Upgrade Compatibility、Test、State Consistency、真实688521 E2E；
-检查开放PR与路径交集；
-合并实现PR；
-核验exact-main源码与Policy disabled。

## W05｜原子Closeout与真实Bark验证

-独立closeout PR将本任务原子更新为DONE generation1；
-closeout main State Consistency成功后，独立producer运行；
-canonical Issue只出现一个stable completion marker；
-Incident最多执行一次Bark POST并上传一个回执Artifact；
-下载Artifact，确认单JSON并运行离线validate；
-通过纯文档观察PR记录实际Run/Artifact/HTTP结果，不修改task state或generation。

## 安全预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_requests_before_closeout: 0
bark_requests_for_closeout_max: 1
bark_automatic_retries: 0
```