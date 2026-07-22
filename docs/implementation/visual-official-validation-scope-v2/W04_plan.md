# W04：测试、Actions与并行开发安全

## 测试矩阵

1. `official_validation_scope`默认值和映射。
2. 非法范围回落到`full_history`。
3. 全历史Runner调用参数为`max_periods=None`。
4. 最近3年/5年/快速范围分别映射12/20/2个报告期。
5. 真实来源冲突映射`COMPLETED_WITH_REVIEW`。
6. 旧完成任务推导F10阶段为`COMPLETED`。
7. 页面不含年度/Q1年份输入，包含全历史范围文案。
8. Artifact过滤不再显示内部键。
9. JavaScript、Ruff、pytest、Visual Execution Control、E2E和Raw Pack回归通过。

## 并行开发策略

- 开始和合并前分别刷新`main`。
- 对PR #21及其他开放PR执行changed-file交集检查。
- 有重叠时先同步和解决，不覆盖对方分支。
- 网络类失败只重跑失败Job；代码失败读取日志后修复。

## 验收

- 功能分支0 behind；
- 所有质量门禁通过；
- PR正文记录范围、兼容性和测试结果；
- 只有在无冲突合并窗口中才合并。
