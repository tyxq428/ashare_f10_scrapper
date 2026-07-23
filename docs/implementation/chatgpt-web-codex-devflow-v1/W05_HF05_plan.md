# W05-HF05 计划：可信 Bot 授权与 Codex 结构化输出交接

## 背景

W05-HF04 已完成并合并：正式 `agent-runtime` Secrets 在入口普通 Job 中可见，Runtime Preflight 与 localhost Forwarder 均已通过。真实薄切片 Run `29995536349` 已进入 `openai/codex-action`，但 Action 返回失败，未生成结构化结果，后续 Scope Guard 与 Targeted Gate 被跳过。

本轮失败发生在明确的 Action 调用边界：任务由仓库自身 `github-actions[bot]` 通过显式 `workflow_dispatch` 启动，而官方 Codex Action 默认拒绝 Bot actor，除非显式配置可信 Bot。当前配置也把 `output-file` 指向 `/tmp`；官方示例使用仓库相对文件或 `final-message` output，因此本轮同时改为从 Action output安全写入工作区外的 `/tmp`。

## 目标

1. 仅允许仓库自身 `github-actions[bot]` 通过显式 `workflow_dispatch` 触发 Codex；
2. 在官方 Codex Action 中显式设置 `allow-bots: true` 与 `allow-bot-users: github-actions[bot]`；
3. Composite action暴露官方 Action 的 `final-message` output；
4. 不再把绝对 `/tmp` 路径作为官方 Action 的 `output-file` input；
5. Caller Job 使用环境变量把结构化 `final-message` 原样写入 `/tmp/codex-result.json`；
6. 保留 Output Schema、localhost Forwarder、一次 Session、低推理强度、Scope Guard、G1、Secret Audit、Manifest、Secret-free Publish 与自动 Gate 接力；
7. 用一个新任务代次从最新 `main` 重跑完整无人值守薄切片。

## 安全边界

- 只有 `github.actor` 为 `tyxq428` 或 `github-actions[bot]` 且事件为显式 `workflow_dispatch` 时允许执行；
- 不使用 `allow-users: *`，不允许任意 Bot；
- 官方 Action 固定完整 Commit SHA；
- `final-message` 不通过 Shell 字符串插值，使用环境变量交给 Python 写入 `/tmp`；
- 结果进入 Secret Audit 后才允许 Publish；
- URL、hostname、Key 和 Model ID仍不进入仓库、日志、Issue、PR或Artifact。

## 修改范围

- `.github/actions/codex-thin-worker/action.yml`
- `.github/workflows/codex-task.yml`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow_codex_environment.py`
- `docs/process/policies/security-and-codex.md`
- `docs/process/runbooks/run-codex-thin-worker.md`
- `scripts/devflow/append_engineering_lessons.py`
- 当前任务状态、结果和恢复文档

## 验收 Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py tests/test_devflow_codex_environment.py
pytest -q tests/test_devflow.py tests/test_devflow_codex_environment.py
现有完整 Test
E2E 688521
真实 Codex Action生成结构化结果
Scope Guard、Targeted Gate、Secret-free Publish、Product Gate、Auto Merge、Post-Merge完整通过
```

## 恢复入口

```yaml
stage: W05_HF05
status: RUNNING
human_intervention_required: false
next_action: authorize_trusted_repository_bot_and_capture_final_message
```
