# W05-HF04 计划：修复 Reusable Workflow 的 Environment Secret 边界

## 背景

正式 `agent-runtime` Environment 已存在三个正确命名的 Secrets，且部署分支为 `No restriction`。安全直接探针在普通 Job 中能够读取三个 Secret 的 presence；同一仓库的 `Codex Task` 通过本地 reusable workflow 调用时，`runtime-preflight.json` 却连续报告 Endpoint、API Key 和 Model 全部缺失，Codex 与 Forwarder均未启动。

这证明问题不在 Secret 名称、值或部署分支规则，而在当前调用边界：Secret-bearing Job 位于被 `workflow_call` 调用的本地 reusable workflow 中。为消除平台行为差异，Environment 必须直接绑定到入口 Workflow 的普通 Job；可复用单元改为本地 composite action，Secret 只作为该 Job 的显式 Action input 使用。

## 目标

1. `Codex Task` 只接受显式 `workflow_dispatch`，不再依赖任务分支 Push 或旧分支中的 Workflow 版本；
2. 在 `codex-task.yml` 内直接定义 `environment: agent-runtime` 的只读 Codex Job；
3. 新增 `.github/actions/codex-thin-worker/action.yml` 作为可复用 Codex 调用单元；
4. 保留 localhost-only Forwarder、一次 Session、`effort: low`、Scope Guard、G1、Secret Audit、Manifest、Secret-free Publish 和显式 Product Gate；
5. 删除不再使用的 `_reusable-codex-thin-worker.yml`，避免双实现和错误复用；
6. 更新静态安全校验、政策、Runbook 和工程经验；
7. 重新从最新 `main` 创建真实薄切片控制分支并显式派发，验证完整无人值守链路。

## 安全边界

- 中转站 URL、hostname、Key 和 Model ID 仍只存在于 `agent-runtime` Environment Secrets；
- Secret-bearing Job 保持 `contents: read`、`persist-credentials: false`；
- Composite action 不写入仓库、不打印 Secret，只连接 `127.0.0.1`；
- Publish、Product Gate、Auto Merge 和 Post-Merge 均不接收 Relay Secrets；
- 诊断只记录 presence、稳定 failure class 和布尔结果；
- 不在 Issue、PR、日志、Artifact 或仓库中公开 Secret 值。

## 修改范围

- `.github/workflows/codex-task.yml`
- 删除 `.github/workflows/_reusable-codex-thin-worker.yml`
- `.github/actions/codex-thin-worker/action.yml`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- `docs/process/policies/security-and-codex.md`
- `docs/process/runbooks/run-codex-thin-worker.md`
- `docs/ENGINEERING_ISSUES_AND_LESSONS.md`
- 当前工作包结果与状态文件

## 验收 Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
现有完整 Test
E2E 688521
直接 Environment Secret presence probe PASS
真实 Codex Thin Worker：Forwarder、Codex、Scope、G1、Publish、Product Gate、Auto Merge、Post-Merge 全链通过
```

## 恢复入口

```yaml
stage: W05_HF04
status: RUNNING
human_intervention_required: false
next_action: implement_direct_environment_job_and_rerun_thin_slice
```
