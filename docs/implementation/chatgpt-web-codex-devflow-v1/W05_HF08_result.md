# W05-HF08 结果：后续 Codex Thin Worker 固定 XHigh

## 状态

```yaml
status: PASS
policy_pull_request: 41
runtime_effort: xhigh
new_task_default: xhigh
legacy_descriptor_read_compatibility: low | xhigh
```

## 实施结果

- 正式 `.github/actions/codex-thin-worker/action.yml` 固定 `effort: xhigh`；
- 新 Task Descriptor 模板固定 `reasoning_effort: xhigh`；
- 自动恢复生成的 State/Codex Recovery Task 固定 `reasoning_effort: xhigh`；
- Workflow 静态安全校验会拒绝生产 Action 回退到 `effort: low`；
- Schema v1 Parser 暂时只读兼容历史 `low` 描述符，以保证已经发布的候选可以继续 Gate/Post-Merge；历史字段不会降低实际模型调用强度；
- 每个 Generation 仍限制为一次 Session、零自动第二 Session，防止 XHigh 成本和失败循环失控。

## 验收

- PR #41 的 State Consistency、完整 Test 和 E2E 全部通过；
- 当前 v3 候选此前已完成 Codex 与 G1，因此政策迁移没有产生无意义的重复模型调用；
- 后续任何新的 Codex 调用均由版本化 Composite Action 强制使用 XHigh。
