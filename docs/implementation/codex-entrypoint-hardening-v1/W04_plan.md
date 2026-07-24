# W04 计划：可信控制平面与任务分支 Data-only

## 实施

- 控制 Policy、Eligibility、Gate、Scope、Secret Audit 必须来自精确默认分支 SHA；
- 任务分支只能提供不可变 Descriptor 和被允许的产品代码；
- 任务分支中的 `.github/**`、`.devflow/**`、`scripts/devflow/**` 不得作为执行控制代码；
- 静态测试证明任务分支修改控制代码不会改变资格结论。

## 验收

`trusted_control_ref=exact_main_sha`，`task_ref_is_data_only=true`。
