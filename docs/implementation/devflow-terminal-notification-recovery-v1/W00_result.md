# W00 结果：完成事件缺失与恢复设计

```yaml
status: PASS
previous_closeout_merge_sha: 5afbb17a574bb850e93d6134719b621e3fdfd10c
previous_task_status: DONE_COMPLETED_PASS
previous_task_notification_generation: 1
previous_task_control_issue: ABSENT
previous_bark_receipt: ABSENT
new_bark_requests: 0
secret_reads: 0
```

## 核验结果

上一任务已原子进入合法canonical DONE状态，ACTIVE_TASKS也同步为DONE；但预期的 `[TASK CONTROL] devflow-bark-delivery-receipt-v1` Issue没有出现。因此目前没有正向证据证明：

-完成事件已从State Consistency dispatch；
-`Devflow Incident`已运行；
-Bark请求已发起；
-回执Artifact已生成。

不能把“没有Issue”解释为Bark请求失败或Secret错误；它只证明当前生产链缺少可观察结果。

## 当前结构缺口

完成生产逻辑作为 `Devflow State Consistency` 的第二个Job存在：

-验证Run和通知生产共享同一Workflow Run；
-Connector只能稳定查询PR关联Run，main push的第二Job难以独立定位；
-生产Job fail-open后，验证Run仍可成功，但没有独立Run作为观察边界；
-恢复时如果简单增加generation，迟到旧事件可能导致重复通知。

## 采用设计

1. 新增独立 `Devflow Terminal State Notification`；
2. 只监听 `Devflow State Consistency` 的成功 `workflow_run`；
3. 只接受source event=push、head branch=main；
4. checkout source `head_sha`并扫描其第一父提交到head的state变化；
5. State Consistency移除内嵌producer；
6. Incident为COMPLETED同时使用generation marker和稳定task completion marker；
7. Workflow重跑、恢复generation和迟到事件均无法发送第二次Bark；
8. producer失败继续fail-open且不进入Auto Recovery。

## 安全结论

该恢复设计不读取Bark Secret、不执行Bark POST、不修改旧任务generation、不重跑历史Workflow。W01可以实施独立producer和稳定完成去重。