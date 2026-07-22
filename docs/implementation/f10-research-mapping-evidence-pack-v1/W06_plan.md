# W06计划：研究专题提取器

## 目标

在通用F10与规范事实层之上，生成研究可以直接消费的专题数据包，而不是让分析师重新浏览数十张接口表。

## 输出专题

```text
profit_quality
segments_and_kpis
research_and_development
capital_structure
capital_events
corporate_governance
risk_events
coverage_gaps
```

## 实施内容

1. 新增确定性专题路由器；
2. 盈利质量：归母→扣非桥、非经常性占比、CFO/利润、简化FCF、研发资本化率；
3. 分部KPI：按record_key重建分部名称、收入、成本、利润、毛利率和来源；
4. 研发：研发费用、研发投入、资本化投入、研发人员和资本化率；
5. 股本：总股本、流通股、回购、股权激励、可转债、限售、解禁、减持和质押；
6. 治理：高管、董事、关联交易、担保、诉讼、处罚和违规；
7. 风险事件：按事件日输出可追溯事件表；
8. 缺口检查：为各专题定义最低必需指标和明确状态；
9. 所有派生结果标记`FACT_CALCULATED`并保存公式和输入Observation ID；
10. 不满足计算条件时输出`UNRESOLVED`，不补零。

## 薄切片

- 归母净利润、扣非净利润和CFO形成盈利质量指标；
- 只有归母、没有扣非时不计算非经常性占比；
- 同一分部record_key的名称、收入和成本被正确合并；
- 研发投入和资本化投入计算资本化率；
- 股权质押进入治理与资本结构，但不重复成为规范事实；
- 缺失核心KPI进入coverage_gaps。

## 验收标准

- 派生公式输入可追溯；
- 缺失数据不补零；
- 事件和期间事实不混用；
- 分部记录不跨record_key合并；
- 专题表拥有稳定`research_fact_id`；
- 单元测试和现有回归工作流通过。

## 恢复入口

```yaml
phase: W06
checkpoint: W06_PLAN_COMMITTED
next_action: implement_research_section_extractors
```
