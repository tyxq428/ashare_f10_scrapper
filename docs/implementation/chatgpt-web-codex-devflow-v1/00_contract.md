# 任务合同：ChatGPT Web Supervisor + GitHub Actions + Codex Thin Worker

## 目标

把现有以 ChatGPT Web 驱动 GitHub 开发的流程升级为可分层读取、可观测、可恢复、可自动验证的执行系统；在不暴露私有 Relay URL、Key 或模型 ID 的前提下，让 Codex 只承担明确、低风险、单 Session 的代码修改。

## 范围

包含：分层 SOP、根/Scoped `AGENTS.md`、canonical state、Policies、Runbooks、Templates、Gate、Failure Bundle、Reusable Codex Worker、Relay Health、Secret Audit、Incident 和 post-merge；以及一个真实低风险薄切片。

不包含：改变 F10、Raw Pack、官方验证或 Research Pack 业务语义；外部 Supervisor、自动合并、无限 Agent 循环、self-hosted runner。

## 安全边界

- 正式 Environment：`agent-runtime`；
- Secret 名称：`AGENT_RESPONSES_ENDPOINT`、`AGENT_API_KEY`、`AGENT_MODEL`；
- Codex 只连接 localhost Forwarder；
- Secret Job 只读，Publish Job 无 Secret；
- 任何越界修改、Manifest 不一致或 Secret 命中立即阻断。

## 验收

1. 分层指令和状态能够由 CI 确定性校验；
2. PR-A 合并后独立基础设施验证通过；
3. 正式环境 Relay 健康检查通过且无泄漏；
4. 一个真实薄切片由单次 Codex Session 完成，只改允许文件；
5. 薄切片 G1、完整 Test 和 post-merge 通过；
6. 通知仅在完成、中断、人工或安全状态产生；
7. 通用问题追加工程经验库；
8. 后续迁移规则和回滚说明完整。

## 人工介入

仅限 Secret/权限缺失、安全阻断、不可自动解决冲突、业务语义或破坏性决策、有限重试耗尽。
