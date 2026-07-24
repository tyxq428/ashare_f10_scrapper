# 总计划：Devflow Bark Terminal Notification v1

## 执行路径

```text
W00 终态事件合同与现状库存
→ W01 通用事件校验、消息渲染与机器清单
→ W02 Incident Workflow 泛化和 Bark 单次投递
→ W03 完成/中断生产者接线与永久静态守卫
→ W04 合并前确定性验证
→ W05 notification-runtime 人工配置、可选一次性 live test、合并和 exact-main
```

## W00｜合同、库存与边界

- 枚举现有 `devflow_notify` 生产者；
- 区分原始 Workflow conclusion 与任务级终态；
- 固化 Bark 是辅助通道、canonical state/Issue 是权威来源；
- 明确去重、单次尝试、无自动重试和 Secret隔离规则。

## W01｜确定性事件处理

新增仓库自有脚本，负责：

- 校验 `task_id`、通知类型、fingerprint、来源 Workflow/Run；
- 从 `ACTIVE_TASKS.yaml` 和对应 `task_state.yaml` 解析任务；
- 对 `COMPLETED` 强制 canonical DONE条件；
- 生成裁剪后的 Issue字段和 Bark JSON；
- 验证目标 URL只指向当前 GitHub仓库；
- 不读取 Secret、不发送网络请求。

新增 `.devflow/notification-channels.yaml`，声明允许通道、Environment、通知类型、最大请求数和无自动重试策略。

## W02｜Incident 与 Bark Transport

- 将 `Devflow Incident` 从单一硬编码任务泛化为 payload中的登记任务；
- 复用 canonical Issue marker做逻辑通知去重；
- 任务没有预登记 Issue时，通过精确标题安全解析或创建一个控制 Issue；
- Bark Job只在首次 Workflow attempt且逻辑通知尚未记录时运行；
- 使用独立 `notification-runtime` Environment和 `BARK_PUSH_URL`；
- 每条逻辑通知最多一次 HTTP POST；
- Bark配置缺失或发送失败只记录安全摘要，不改变任务结果。

## W03｜事件生产与永久守卫

- 所有现有 `devflow_notify` payload显式携带 `task_id`；
- 完成通知只能在最终 closeout 已持久化后产生；
- 中断、人工和安全事件继续由现有确定性分类产生；
- Auto Recovery不得监听或重跑 `Devflow Incident`；
- Validator扫描唯一 Bark请求位置、禁止 raw `workflow_run` 通知和禁止 `agent-runtime`/模型耦合。

## W04｜确定性验证

- Ruff和单元测试；
- State Consistency与Workflow Validator；
- 本地/mock HTTP验证，不触发真实 Bark；
- 完整 Test和真实 688521 E2E；
- Codex、Responses、Relay Secret和历史 Workflow调用均为0。

## W05｜平台配置与完成

人工在 GitHub UI：

1. 创建或确认 `notification-runtime`；
2. 仅允许 `main`；
3. 不设置 Required Reviewer，保证终态通知可自动发送；
4. 关闭管理员绕过（若页面提供）；
5. 添加 Environment Secret `BARK_PUSH_URL`，值为 Bark App复制的完整推送URL；
6. 不在聊天、PR或日志中粘贴该值。

配置完成后，可通过一次性、精确确认且 `run_attempt=1` 的临时 Workflow发送一条 live test；成功后立即删除临时 Workflow。随后合并、运行 exact-main并完成 canonical state。

## 预算

```yaml
codex_calls: 0
responses_paid_probes: 0
relay_secret_reads: 0
historical_codex_reruns: 0
bark_live_tests_before_human_confirmation: 0
bark_live_tests_max: 1
```