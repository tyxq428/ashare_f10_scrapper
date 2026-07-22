# F10研究映射包＋官方原文证据包：最终实施报告

## 最终状态

```yaml
phase: W09
status: COMPLETED
progress: 100%
branch: feature/f10-research-mapping-evidence-pack-v1
pull_request: 21
human_intervention_required: false
next_action: merge_PR21
```

## 目标达成

本次实施将现有F10采集、官方验证、Raw Pack和交叉验证能力升级为可直接服务投研系统的两项标准产品：

1. **F10 Research Mapping Pack**：将多源宽表与事件记录映射为规范事实、研究视图和可增量更新的研究输入；
2. **Official Primary-source Evidence Pack**：将规范事实穿透到官方文档、页码、原始行、版本链和文件哈希。

最终链路：

```text
F10 / Official / Raw Pack
→ Source Facts
→ Canonical Observations
→ Research Sections
→ Fact Lineage
→ Evidence Graph
→ JSON / Excel / Parquet / DuckDB
→ CLI / API / Web UI
```

## W01—W09完成情况

- **W01**：修复附注号、页码和表序号误识别为金额的问题；增加`PARSE_SUSPECT`隔离。
- **W02**：增加`as_of_date`、`available_at`、文档版本链和边界文档，消除未来信息泄漏。
- **W03**：增加指标级比较方法、绝对/相对容差、根因分类；拆分覆盖率与准确率。
- **W04**：建立Source Fact、Canonical Observation、Research View和Fact Lineage。
- **W05**：建立统一Evidence Graph，实现事实到官方原文的穿透。
- **W06**：生成盈利质量、分部KPI、研发、资本结构、资本事项、治理、风险和缺口专题。
- **W07**：实现Research Pack多格式导出、CLI、检查点、缓存、断点恢复和完整性验证。
- **W08**：完成多样本E2E、真实002352 CNINFO验证、缓存/稳定ID/可移动性和性能验收。
- **W09**：完成独立API、Web UI、运行预设、增量Diff、主分支语义同步和最终回归。

## 关键正确性改进

### 解析正确性

类似：

```text
递延所得税资产 七、29
```

不再生成29元高置信事实。无法可靠恢复金额时，事实进入`PARSE_SUSPECT`，不参与规范事实选择、准确率和会计勾稽。

### Point-in-Time

事实与文档记录：

```text
report_date/effective_at
published_at
available_at
retrieved_at
as_of_date
supersedes_document_id
is_boundary
```

只有`available_at <= as_of_date`的文档才能进入研究基线。

### 覆盖与准确率

不再用一个总匹配率混合表示解析覆盖和数值准确性，分别输出：

```text
classification_coverage
report_discovery_coverage
target_extraction_coverage
comparison_coverage
comparison_accuracy
evidence_completeness
suspicious_extraction_rate
unresolved_rate
```

### 规范事实和冲突

来源优先级为：

```text
官方直接披露
> 官方派生
> F10直接事实
> 平台特有事实
```

高质量来源发生真实冲突时：

```text
status = SOURCE_CONFLICT
canonical value = null
```

系统不会静默覆盖。

## 研究专题输出

Research Pack可生成：

```text
company_master
financial_statements
quarterly_and_ttm
profit_quality
segments_and_kpis
research_and_development
capital_structure
capital_events
corporate_governance
risk_events
market_and_consensus
coverage_and_gaps
```

计算事实保存公式和输入Observation ID；输入不足时返回`UNRESOLVED`，不补零。

## 工程能力

- JSON、Excel、Parquet、DuckDB多格式输出；
- Manifest、Summary、Quality、Checkpoint和Incremental Diff；
- 输入指纹覆盖数据文件、截止日、预设、本体、注册表和提取器版本；
- 相同输入缓存命中；语义变化自动失效；
- 中断后按阶段恢复；
- 包移动后仍可重新打开；
- Evidence Graph和Lineage完整性验证；
- `research-full`和`thin-slice`两种预设；
- CLI、API和独立Web页面。

## 最终质量闸门

合并前要求：

- PR处于Ready for Review；
- 与`main`可合并；
- Test通过；
- Research Pack W08 Matrix通过；
- 688521 E2E通过；
- Official Full-History Validation通过；
- Raw Pack E2E通过；
- 无未解决Review Thread；
- W01—W09计划和结果Markdown完整。

## 后续增量方向

本轮范围完成后，后续可按独立任务推进：

- 北交所官方来源接入；
- 更多附注和非标准表格解析器；
- 行业专属KPI本体；
- 全市场批量Research Pack调度；
- 研究系统下游模型和报告消费；
- 质量指标长期监控与漂移告警。
