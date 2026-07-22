# W06结果：研究专题提取器

## 状态

```yaml
phase: W06
status: COMPLETED
last_successful_step: deterministic_research_sections_verified
next_action: W07_research_pack_exports_and_resume
human_intervention_required: false
```

## 完成内容

1. 新增`ResearchSectionExtractor`和`ResearchSectionPack`。
2. 自动生成八类研究专题：
   - `profit_quality`
   - `segments_and_kpis`
   - `research_and_development`
   - `capital_structure`
   - `capital_events`
   - `corporate_governance`
   - `risk_events`
   - `coverage_gaps`
3. 盈利质量确定性计算：
   - 归母净利润与扣非归母净利润差额；
   - 非经常性损益占归母净利润；
   - CFO/扣非归母净利润；
   - 简化自由现金流；
   - 研发投入资本化率。
4. 每个派生事实保存：
   - `FACT_CALCULATED`状态；
   - 公式；
   - 输入Observation ID；
   - 稳定`research_fact_id`。
5. 缺少任一输入时输出`UNRESOLVED`，数值保持空，不补零。
6. 分部数据严格按`record_key`、报告期、family和dataset重建，避免跨分部拼接。
7. 缺少毛利或毛利率时，可由同一分部记录中的收入和成本确定性计算，并单独标记计算状态。
8. 研发、股本、资本事项、治理和风险使用确定性字段/家族路由生成专题表。
9. `coverage_gaps`区分：
   - 指标真实为0但已经披露；
   - 当前没有可靠规范事实。
10. 专题API已经从`research_mapping`包导出。

## 薄切片结果

| 场景 | 结果 |
|---|---|
| 归母100、扣非80 | 非经常性20，占比20% |
| CFO150、扣非80 | 现金转化1.875x |
| CFO150、CapEx30 | 简化FCF120 |
| 研发投入20、资本化5 | 资本化率25% |
| 缺少扣非利润 | `UNRESOLVED`，不补零 |
| 两个分部不同record_key | 独立重建，未串行 |
| 真实披露值为0 | 标记`PRESENT`，不当作缺失 |
| 未形成规范事实 | 标记`MISSING`并提示不得解释为0 |

## 问题排查

首次CI在Ruff阶段发现：

- 一个未使用的`re`导入；
- 循环内部闭包触发`B023`风险。

处理方式：重构专题提取器，移除循环变量闭包，将比例计算和分部字段选择抽为显式参数函数。修复后Lint、测试和真实E2E全部通过。

## 自动验证

| Workflow | Run | 结果 |
|---|---:|---|
| Test | 582 | success |
| E2E 688521 | 212 | success |
| Official Validation 688521 | 164 | success |
| Raw Pack 688521 E2E | 64 | success |

## 质量指标

```yaml
new_extractor_tests: 6
formula_traceability: 1.0
zero_fill_cases: 0
segment_cross_record_merges: 0
failed_tests_after_fix: 0
blocking_items: 0
```

## 后续

W07将把F10源事实、官方事实、规范事实、证据图和研究专题打包为JSON、Excel、Parquet和DuckDB，增加CLI、幂等检查点和断点恢复。
