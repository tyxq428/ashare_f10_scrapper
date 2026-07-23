# 数据与研究语义政策

## 基本状态

- `FACT_DIRECT`：来源直接披露；
- `FACT_CALCULATED`：由已核验输入和明确公式计算；
- `FACT_ZERO_EXPLICIT`：来源明确披露为 0、无或不适用；
- `PARSE_SUSPECT`：解析结果可疑，保留证据但隔离；
- `SOURCE_CONFLICT`：可比来源存在实质差异，不静默选值；
- `BOUNDARY_DISCLOSURE`：仅能确认披露边界；
- `UNRESOLVED`：当前条件下无法可靠形成事实。

## 禁止推断

`NO_MATCH`、空字段、权限阻断、来源未接入、报告未披露、PDF 提取失败或索引未命中，都不得解释为 0、不存在、无风险或无订单。

## 时间与版本

- 研究任务必须记录 `as_of_date`；
- 只使用 `available_at <= as_of_date` 的文档；
- 更正版在截止日前可得时可优先，截止日后版本进入 boundary，不泄漏未来信息；
- 事实期间、发布日期、可得日和抓取时间不得混用。

## 质量指标

准确率、比较覆盖、目标提取覆盖、证据完整度和未解决率分别报告。缺少官方事实降低覆盖率，不进入准确率分母。

## 执行与研究结论

`execution_status == COMPLETED` 可以与 `research_acceptance_status == REVIEW_REQUIRED` 同时成立。真实来源冲突和覆盖缺口必须展示为“完成，需复核”，不能伪装为程序失败，也不能为了绿灯隐藏。
