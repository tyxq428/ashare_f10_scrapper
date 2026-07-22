# W03计划：对账语义、指标级容差与质量指标

## 目标

将“覆盖不足”和“已比较值的准确性”彻底拆开，并根据指标类型选择数值、文本、日期、集合或事件比较方法。

## 基线问题

现有`comparable_match_rate`把以下项目放入同一分母：

- 已完成双源比较的事实；
- 官方尚未解析的事实；
- 未加载报告期；
- 官方独有或东方财富独有事实；
- 等待未来免费来源的事实。

因此1.245%主要代表覆盖率，不是准确率。

## 实施内容

1. 扩展字段注册表条目：
   - `comparison_method`
   - `canonical_unit`
   - `absolute_tolerance`
   - `relative_tolerance`
   - `display_decimals`
2. 建立默认容差策略：
   - 财务金额：绝对容差＋相对容差；
   - 每股指标：按显示小数位；
   - 百分比：基点容差；
   - 股数/人数：整数容差；
   - 日期：规范日期完全匹配；
   - 文本/名单：规范文本或集合比较。
3. 比较器输出根因字段和实际采用的比较方法。
4. 新增独立质量指标：
   - classification_coverage
   - report_discovery_coverage
   - document_parse_rate
   - target_extraction_coverage
   - comparison_coverage
   - comparison_accuracy
   - evidence_completeness
   - suspicious_extraction_rate
   - unresolved_rate
5. 保留旧`comparable_match_rate`作为兼容别名，但标记deprecated。
6. 验收状态使用真实冲突、分类缺口、官方源状态和覆盖缺口，不把覆盖缺口当成准确性失败。

## 薄切片

- 亿元/万元/元单位归一；
- 大额财务数字的相对容差；
- EPS小数位容差；
- 百分比基点容差；
- 日期和文本规范化；
- 只有匹配与真实冲突进入准确率分母。

## 验收标准

- 548匹配、0真实冲突时准确率应为100%，而不是1.245%；
- 覆盖率仍如实反映未加载与未解析事实；
- 每条比较记录可解释比较方法、容差和根因；
- 旧输出字段保持兼容；
- Test、Official Validation、E2E通过。

## 恢复入口

```yaml
phase: W03
checkpoint: W03_PLAN_COMMITTED
next_action: implement_metric_specific_comparison_and_quality_metrics
```
