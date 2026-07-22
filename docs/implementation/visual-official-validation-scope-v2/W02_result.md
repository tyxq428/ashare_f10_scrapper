# W02结果：全历史官方验证后端集成

## 状态

`COMPLETED`

## 实现

- 新增产品化范围：`latest=2`、`recent_3y=12`、`recent_5y=20`、`full_history=None`。
- 默认范围改为`full_history`，由F10事实表自动获得报告期，并通过证券生命周期自动识别上市日期、上市前期间、摘要式报告和尚未披露期间。
- 可视化任务改为调用`run_full_cross_validation`，不再调用“两份报告薄切片”Runner。
- 旧请求中的年度/Q1字段仍可读取，但网页不再展示，也不参与正式可视化主流程。
- 官方验证增加发现、下载、解析、对账、导出等阶段级进度。
- `FAIL_SOURCE_CONFLICT`、`PASS_WITH_COVERAGE_GAPS`、`PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE`及其他非`PASS`验收状态统一显示“完成，需复核”，不误报为代码崩溃。
- 长时外部命令改为流式输出和固定心跳。
- Raw Pack与官方验证并行完成后，最终`artifacts.json`执行原子合并，避免最后写入覆盖。

## 兼容性

- 旧Sidecar自动补充新范围默认值；
- 原有任务、Raw Pack API和F10主流程保持兼容；
- 官方来源真实冲突继续完整保留，不为追求PASS而隐藏。

## 验收

- 范围映射与回退测试通过；
- 全历史Runner调用参数和进度回调测试通过；
- 冲突、覆盖缺口、部分来源不可用状态测试通过；
- 并行Artifact清单回归测试通过。
