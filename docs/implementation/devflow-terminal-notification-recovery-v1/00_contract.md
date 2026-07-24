# 任务合同：Devflow Terminal Notification Recovery v1

## 目标

修复 canonical `DONE` closeout 后完成事件未产生可观察 task-control Issue 的可靠性缺口，并使用本任务自身的真实 `COMPLETED` generation 验证：

```text
State Consistency PASS
→ terminal completion producer
→ devflow_notify
→ canonical Issue
→ at most one Bark POST
→ safe delivery receipt Artifact
```

## 已知事实

- `devflow-bark-delivery-receipt-v1` 已在 main 达到 `DONE / COMPLETED / PASS`；
- closeout后的 canonical Issue 未出现，因此不能证明Bark请求已发起；
- 当前完成生产逻辑内嵌在 `Devflow State Consistency` 的第二个Job中；
- Bark Transport、回执Artifact和Issue索引实现已通过完整确定性Gate；
- 不应通过Gmail、UI Re-run或读取Secret来确认结果。

## 范围

1. 将完成事件生产者改为独立的 `workflow_run` 成功后继Workflow；
2. 只接受 `Devflow State Consistency` 在 `main` 的成功push Run；
3. 扫描精确source head相对第一父提交的canonical state变化；
4. 移除State Consistency内嵌通知Job，保持单一生产者；
5. 为 `COMPLETED` 增加跨generation的稳定task marker，防止恢复generation或迟到事件重复Bark；
6. 更新清单、Validator、测试、Policy与Runbook；
7. 用本任务closeout执行一次真实Bark并下载回执Artifact。

## 硬约束

```yaml
codex_policy: disabled
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
synthetic_bark_tests: 0
bark_requests_before_final_closeout: 0
bark_requests_for_final_closeout_max: 1
bark_automatic_retries: 0
bark_secret_value_reads_by_chatgpt: 0
```

## 禁止

- 不读取、显示、复制、哈希或变换 `BARK_PUSH_URL`；
- 不重跑历史或现有Bark Incident；
- 不通过GitHub UI Re-run补发；
- 不创建任意payload的测试按钮；
- 不让通知生产/dispatch失败改变canonical task state；
- 不从原始Workflow失败直接通知；
- 不调用Codex、Responses、Relay Health、Secret Audit或历史模型Workflow。

## 完成定义

- 新生产者在精确main的State Consistency成功后运行；
- Incident仍只监听 `devflow_notify`；
- single producer和stable completion marker通过静态/行为测试；
-完整Test、State Consistency、Upgrade Compatibility和真实688521 E2E通过；
-合并后本任务DONE closeout只产生一个canonical完成通知；
-真实Bark回执显示 `request_initiated=true`，并明确HTTP结果；
-回执Artifact通过离线validate且不含Secret/Endpoint/响应内容。