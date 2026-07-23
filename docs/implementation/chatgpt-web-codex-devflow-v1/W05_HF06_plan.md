# W05-HF06 计划：Product Gate 使用 Merge Base 进行范围校验

## 背景

真实无人值守薄切片 `resilient-command-terminal-status-auto-v3` 已完成以下步骤：

- Runtime Preflight：PASS；
- localhost Forwarder：PASS；
- Codex Session：PASS；
- 结构化结果：PASS；
- Scope Guard：PASS；
- Targeted Gate：PASS；
- Secret Audit：PASS；
- Secret-free Publish：PASS；
- 显式 Product Gate dispatch：PASS。

Product Gate Run `29997841634` 在进入 Full Gate 前失败。产品分支只修改两个获准文件，但 Product Gate 使用：

```text
git diff origin/main HEAD
```

此时 `main` 已经包含薄切片启动后的观察/编排提交，而产品分支从任务创建时的批准基线分叉。双点 Diff 会把 `main` 独有的提交也计算为差异，从而把与产品任务无关的 Workflow 变化误判为 Scope Violation。

## 目标

1. 初始产品范围校验使用 `git merge-base origin/main HEAD` 作为 Base，只检查候选分支相对共同祖先新增的变化；
2. 验证任务描述中的 `expected_base_sha` 是候选分支祖先，防止替换为不相关历史；
3. Scope Step 产生结构化 `scope-result.json`；
4. Scope 真实失败时跳过 Full Gate、Recovery 和自动合并，并由 Auto Recovery按 `SECURITY_BLOCKED` 处理；
5. Full Gate失败仍按原政策最多派发一个受限 Recovery Generation；
6. 若 `main` 在候选生成后推进，合并前继续 rebase到最新 `main`，重新运行 Scope与 Full Gate；
7. 不修改 F10、Raw Pack、官方验证、Research Pack 或本次 Codex产品补丁。

## 安全边界

- Merge Base只能用于识别候选分支自共同祖先以来的新增文件；
- `expected_base_sha`祖先校验仍保留任务起点约束；
- rebase后必须再次以最新 `origin/main` 执行范围校验；
- Scope失败不得自动扩大 `allowed_files`、不得调用 Codex绕过安全控制；
- Scope Artifact只包含路径和状态，不包含任何 Secret。

## 修改范围

- `.github/workflows/devflow-product-gate.yml`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- `docs/process/policies/gates-and-merge.md`
- `docs/process/runbooks/automatic-recovery.md`
- `scripts/devflow/append_engineering_lessons.py`
- 当前状态、结果与恢复文档

## 验收 Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py tests/test_devflow_codex_environment.py
pytest -q tests/test_devflow.py tests/test_devflow_codex_environment.py
现有完整 Test
E2E 688521
使用已有 v3 产品分支重新运行 Product Gate：Scope、Full Gate、rebase、自动合并全部通过
exact-main Post-Merge通过
```

## 恢复入口

```yaml
stage: W05_HF06
status: RUNNING
human_intervention_required: false
next_action: implement_merge_base_scope_and_rerun_existing_product_candidate
```
