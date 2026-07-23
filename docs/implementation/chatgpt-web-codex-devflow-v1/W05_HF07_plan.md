# W05-HF07 计划：Product Gate Git身份与合并边界集中恢复

## 背景

W05-HF06 修复已生效，Product Gate Run `29998952457` 已通过：

- Merge Base Scope：PASS；
- Full Product Gate：PASS；
- 低风险自动合并步骤进入执行。

合并步骤在 rebase 创建新提交时失败，安全诊断明确为：

```text
Committer identity unknown
fatal: empty ident name ... not allowed
```

候选代码和Gate均无问题。这是确定性的执行环境机械缺口，不应要求用户介入。当前 Workflow还把 merge step设为`continue-on-error`并直接发送`HUMAN_REQUIRED`，导致 Workflow 表面成功、Post-Merge被跳过、Auto Recovery无法统一分类。

## 目标

1. Product Gate在任何 rebase/merge前固定设置仓库级 Git Bot identity；
2. 保留低风险自动合并的范围、Gate、冲突和权限边界；
3. 删除 Product Gate 内直接发送 merge-failure通知的逻辑；
4. merge失败后让 Workflow真实失败，由`Devflow Auto Recovery`统一分类；
5. `rebase conflict / branch protection / permission`分类为`HUMAN_REQUIRED`；
6. Git identity缺失通过固定配置永久消除，不消耗 Codex额度；
7. 修复合并后，重新运行已通过Codex/Scope/Gate的v3候选，不重新调用模型；
8. 自动合并成功后显式进入 exact-main Post-Merge。

## 安全边界

- Git identity固定为`github-actions[bot]`和官方noreply地址，不使用用户凭据；
- 不启用强推、不绕过分支保护、不自动解决冲突；
- Merge step失败必须返回非零，由统一恢复控制器做最终通知决策；
- 不修改本次Codex产品补丁、不访问Relay Secrets。

## 修改范围

- `.github/workflows/devflow-product-gate.yml`
- `scripts/devflow/recovery_policy.py`
- `scripts/devflow/validate_workflows.py`
- `tests/test_devflow.py`
- `tests/test_devflow_codex_environment.py`
- `docs/process/policies/gates-and-merge.md`
- `docs/process/runbooks/automatic-recovery.md`
- `scripts/devflow/append_engineering_lessons.py`
- 当前状态与恢复文档

## 验收Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py tests/test_devflow_codex_environment.py
pytest -q tests/test_devflow.py tests/test_devflow_codex_environment.py
现有完整Test
E2E 688521
已有v3候选重新运行Product Gate：rebase、Full Gate、merge、Post-Merge全部通过
```

## 恢复入口

```yaml
stage: W05_HF07
status: RUNNING
human_intervention_required: false
next_action: configure_bot_identity_and_fail_merge_boundary_through_auto_recovery
```
