# W05-HF01 计划：Post-Merge运行时预检与Incident去重

## 背景

PR-A合并后的独立运行暴露了三个执行层问题：

1. Canonical State仍指向已合并功能分支，导致`main`分支一致性校验失败；
2. 多个通知Workflow并发创建了重复任务控制Issue；
3. 正式Codex薄切片在localhost Forwarder启动前失败，Codex未被调用，但原流程没有安全且可操作的失败分类。

## 目标

- 增加不输出Endpoint、Key或模型ID的运行时预检；
- 让Forwarder启动失败产生安全状态文件和稳定错误分类；
- 将Codex诊断Handoff全部移出仓库工作区，避免Scope Guard自污染；
- 串行化所有任务Incident并按稳定事件键去重；
- 保留Secret Job只读、Publish Job无Relay Secret的权限边界；
- 修复后重新执行devflow定向测试、Workflow静态安全检查和完整Test。

## 修改范围

- `scripts/devflow/runtime_preflight.py`
- `scripts/devflow/private_responses_forwarder.py`
- `tests/test_devflow.py`
- `.github/workflows/_reusable-codex-thin-worker.yml`
- `.github/workflows/devflow-incident.yml`
- `.github/workflows/devflow-infrastructure-incident.yml`
- `docs/ENGINEERING_ISSUES_AND_LESSONS.md`
- 当前工作包计划、结果和恢复状态文档

## 安全约束

- 不读取、打印、提交或上传真实Relay URL、hostname、API Key或模型ID；
- 原始Forwarder stderr不进入Artifact；
- 诊断只包含presence、shape、稳定failure class和布尔结果；
- 不调用Codex进行本Hotfix；
- 不修改F10、Raw Pack、官方验证或Research Pack业务逻辑。

## 验收Gate

```text
python scripts/devflow/validate_workflows.py
ruff check scripts/devflow tests/test_devflow.py
pytest -q tests/test_devflow.py
python -m compileall -q src scripts
现有完整 Test Workflow
Devflow State Consistency
```

## 恢复规则

本Hotfix通过后，更新已有Codex控制分支的`dispatch_generation`，重新触发同一个真实薄切片。第一次失败发生在Codex调用前，因此不计入单次Codex Session预算。
