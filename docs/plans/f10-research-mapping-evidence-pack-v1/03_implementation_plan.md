# 分阶段实施计划

> 目标：在不破坏现有F10、官方验证和Raw Pack功能的前提下，逐步交付“F10研究映射包＋官方原文证据包”。  
> 当前状态：阶段0—1（任务合同与基线审计）已完成；尚未修改业务代码。

## 1. 执行原则

1. 每个阶段开始前提交对应计划Markdown；
2. 每个阶段结束后提交结果、指标、错误与下一阶段Markdown；
3. 正常通过后自动继续，不等待人工确认；
4. 每个阶段至少保存：代码提交、状态JSON、测试日志、输出样本和恢复入口；
5. 先修正确性，再扩大覆盖，再优化界面和性能；
6. 新旧输出并行一段时间，避免破坏现有使用方式；
7. 与PR #18和PR #16保持边界，必要时同步main后继续；
8. 所有解析器首次扩展先在688521薄切片验证，再跑002352回归；
9. 任何可疑解析不得以高置信官方事实进入规范层；
10. 未加载、未披露、未实现和未解析必须使用不同状态。

## 2. 工作包总览

| 工作包 | 名称 | 主要成果 | 依赖 | 预计代码风险 |
|---|---|---|---|---:|
| W00 | 任务合同与基线 | 本目录规划文档 | 无 | 无 |
| W01 | 解析正确性闸门 | 修复附注号伪事实、可疑解析状态 | W00 | 高 |
| W02 | 时点与版本控制 | `as_of_date`、版本链、边界过滤 | W01 | 高 |
| W03 | 对账语义与质量指标 | 指标级容差、覆盖/准确率拆分 | W01 | 中高 |
| W04 | 研究本体与规范事实 | metric registry、canonical facts、lineage | W01-W03 | 高 |
| W05 | 统一官方证据图 | Raw Pack与官方报告统一文档/证据模型 | W02-W04 | 高 |
| W06 | 研究章节解析器 | 盈利质量、分部、研发、股本、事件 | W04-W05 | 高 |
| W07 | 研究包导出与CLI | Excel/Parquet/DuckDB/JSON、预设、恢复 | W04-W06 | 中 |
| W08 | 全量E2E和兼容性 | 多市场样本、性能、迁移文档 | 全部 | 中高 |
| W09 | UI/API对接 | 可视化消费稳定契约 | W07-W08；协调PR#16 | 中 |

## 3. W00：任务合同与基线审计

### 状态

已完成。

### 已提交文档

- `00_task_contract.md`；
- `01_baseline_audit_688521.md`；
- `02_target_architecture.md`；
- 本文；
- `04_acceptance_matrix.md`（随本阶段提交）。

### 质量闸门

- 代码未修改；
- 样本输出已完成结构、数据、逻辑和来源审计；
- 已识别P0伪事实问题；
- 已定义目标数据契约和实施顺序。

### 恢复入口

```text
branch: plan/f10-research-mapping-evidence-pack-v1
next_action: W01 parser correctness thin slice
```

## 4. W01：官方解析正确性闸门

## 4.1 目标

先消除能够产生伪官方事实的解析错误，并建立“宁可不提取，也不生成高置信假事实”的质量政策。

## 4.2 首个薄切片

必须覆盖：

1. 正常单行财务项目；
2. 带附注编号且金额同一行；
3. 标签和金额跨行；
4. 只有附注号、金额在下一行；
5. 横线表示明确零或不适用；
6. 合并表与母公司表；
7. 续表和跨页；
8. 负数括号；
9. 单位明确、继承和缺失；
10. 688521的“递延所得税资产 七、29”真实回归。

## 4.3 拟修改模块

优先：

- `validation/documents/pdf_parser.py`；
- `validation/models.py`；
- `cross_validation/adapters.py`（若需传递解析质量）；
- `cross_validation/comparator.py`（排除PARSE_SUSPECT）；
- `tests/test_official_validation.py`；
- 新增固定PDF/文本fixture目录。

## 4.4 设计任务

1. 建立附注编号token识别器；
2. 明确金额列，不再只依赖数字候选顺序；
3. 实现有限状态的wrapped-row重建；
4. 为每个事实记录解析路径和质量flags；
5. 增加`PARSE_SUSPECT`和`PARSER_COVERAGE_GAP`；
6. 将置信度从固定high改为规则评分；
7. 可疑事实保留证据但不参与规范事实与双源准确率；
8. 运行会计逻辑、前后期和数量级sanity checks；
9. 输出`suspicious_extractions`队列；
10. 重新生成688521两期薄切片并对比变化。

## 4.5 验收

- 两个29伪事实不再作为金额事实；
- 正确金额若能跨行重建则提取，否则明确标记缺口；
- 旧正常测试全部通过；
- 新解析fixture全通过；
- 688521被比较的核心三表事实不下降超过可解释范围；
- 无新增真实冲突；
- 生成阶段结果文档：
  - `10_W01_parser_correctness_plan.md`；
  - `11_W01_parser_correctness_result.md`。

## 4.6 检查点

- `checkpoint/W01_before_parser_change`；
- `checkpoint/W01_after_thin_slice`；
- 状态JSON记录失败fixture和重试队列。

## 5. W02：Point-in-time与版本链

## 5.1 目标

确保任意历史研究截止日只使用当时可得的信息，并保留更正/修订的完整版本链。

## 5.2 任务

1. CLI加入`--as-of-date`；
2. API任务合同加入`as_of_date`；
3. SSE/CNINFO发现接口按截止日过滤；
4. 查询可晚于截止日执行，但选入基线的文档必须`available_at <= as_of_date`；
5. 保存原版、更正版、修订版和撤回版；
6. 建立`supersedes_document_id`；
7. 事实建立版本链；
8. 截止日后事实进入`BOUNDARY_DISCLOSURE`或完全排除，按任务参数决定；
9. cache和manifest包含as-of-date与版本策略；
10. 增加未来信息泄漏测试。

## 5.3 重点测试

- 截止日在原版和更正版之间时选择原版；
- 截止日在更正版之后时选择更正版；
- 后发布但报告期较早的文件不能自动回填；
- 重复运行同一as-of-date结果稳定；
- 当前日期运行仍与现有默认行为兼容。

## 5.4 文档

- `20_W02_point_in_time_plan.md`；
- `21_W02_point_in_time_result.md`。

## 6. W03：对账语义、容差和指标重构

## 6.1 目标

让质量指标准确表达：系统在哪里覆盖、在哪里比较、比较是否一致。

## 6.2 任务

1. 从全局绝对差1元改为指标级容差；
2. 本体配置比较方法：numeric/text/set/date/formula；
3. 规范单位后再比较；
4. 明确累计、独立季度、TTM和时点事实；
5. 明确合并、母公司和实体范围；
6. 将市场价格派生和平台口径移出官方报告比较；
7. 重构状态根因；
8. 拆分质量指标；
9. 对“0冲突但低覆盖”给出准确描述；
10. 对官方仅有事实区分正常补充与可疑解析。

## 6.3 新指标

```text
classification_coverage
report_discovery_coverage
document_download_rate
document_parse_rate
target_extraction_coverage
comparison_coverage
comparison_accuracy
official_only_rate
source_only_rate
evidence_completeness
suspicious_extraction_rate
unresolved_rate
```

## 6.4 验收

- 688521不再将1.245%显示为核心“准确率”；
- 同一输出同时显示低覆盖与高已比较准确率；
- 不适用字段不进入可比分母；
- 比率、每股、人数、金额和百分比使用不同容差；
- 文档：
  - `30_W03_reconciliation_metrics_plan.md`；
  - `31_W03_reconciliation_metrics_result.md`。

## 7. W04：研究本体和规范事实层

## 7.1 目标

建设F10研究映射包的核心：从源字段上下文转为稳定`metric_id`和`observation_id`。

## 7.2 任务

1. 建立ontology schema；
2. 建立metric registry；
3. 将现有field validation registry拆为：
   - source classification；
   - metric mapping；
   - validation policy；
4. 建立SourceFact、CanonicalFact、FactLineage模型；
5. 建立多对一优先级和冲突规则；
6. 建立财务、盈利质量、分部、KPI、股本、治理、市场预测模块；
7. 将公式事实记录输入血缘；
8. 建立版本化schema；
9. 输出canonical parquet和DuckDB；
10. 保持原始F10输出不变，新增研究包输出。

## 7.3 首批Metric范围

优先覆盖：

- 三张表核心项目；
- 扣非与非经常性；
- 资本开支与FCF；
- 应收、存货、合同资产；
- 研发费用与资本化；
- 总股本、流通股、回购、激励、可转债；
- 分部收入与利润；
- 当前价格、市值、一致预期（来源特定）。

## 7.4 验收

- 一个经济事实只有一个首选observation；
- 所有重复源记录保留lineage；
- 规范事实可稳定增量更新；
- 版本变更不改变历史ID；
- 文档：
  - `40_W04_ontology_mapping_plan.md`；
  - `41_W04_ontology_mapping_result.md`。

## 8. W05：统一官方证据图

## 8.1 目标

将Raw Pack、官方定期报告、临时公告和规范事实连接到统一document/evidence模型。

## 8.2 任务

1. 统一OfficialDocument和SourceDocument；
2. 所有文档生成稳定document_id；
3. Raw Pack和cross-validation复用同一文档registry；
4. F10公告ID/标题作为官方发现种子；
5. 保存原始文档、规范文本、页索引和证据索引；
6. 每个规范事实关联一个或多个evidence_id；
7. 相对路径可随项目包移动；
8. 原文不可得时明确权限/来源状态；
9. 证据哈希和解析版本写入manifest；
10. 生成可点击/可定位Excel证据索引。

## 8.3 文档类型优先级

1. 定期报告及更正；
2. 招股书和问询回复；
3. 业绩预告/快报；
4. 股本、回购、激励、可转债和融资公告；
5. 重大合同和资本运作；
6. 监管、处罚、诉讼和担保；
7. IR演示、调研和经营数据；
8. 行业官方来源。

## 8.4 验收

- 关键事实能从规范事实穿透到原始PDF页/行；
- 原始文件、哈希和版本链完整；
- Raw Pack和cross-validation不再重复下载同一文件；
- 文档：
  - `50_W05_evidence_graph_plan.md`；
  - `51_W05_evidence_graph_result.md`。

## 9. W06：研究章节解析器

## 9.1 目标

从“只解析核心三表”扩展到完整首次覆盖常用事实，但每个章节独立开发和验证。

## 9.2 子工作包

### W06A 盈利质量

- 非经常性损益明细；
- 政府补助；
- 处置与公允价值；
- 减值；
- 研发资本化；
- 股份支付；
- 收入确认政策；
- 现金流补充。

### W06B 分部和经营KPI

- 分部收入、成本、利润；
- 地区和产品结构；
- 产销量/客户数/价格等公司披露KPI；
- 仅抽取披露事实，不自动生成行业判断。

### W06C 股本与资本结构

- 当前股本；
- 回购和库存股；
- 股权激励；
- 可转债；
- 增发/重组股份；
- 解禁与减持；
- 前瞻股本桥的可计算输入。

### W06D 治理和风险

- 控股股东；
- 质押；
- 关联交易；
- 担保；
- 诉讼；
- 处罚；
- 审计意见；
- 管理层与员工结构。

## 9.3 开发纪律

- 每个章节单独配置、fixture、指标和文档；
- 不以一个通用正则解析所有章节；
- 新章节不影响核心三表；
- 首次上线扩大抽样；
- 发现系统错误回溯全部同章节结果。

## 10. W07：导出、CLI和恢复

## 10.1 任务

1. 新增研究映射包导出器；
2. 新增证据包导出器；
3. 输出manifest和schema版本；
4. 增加`thin-slice`与`research-full`预设；
5. 增加`as_of_date`；
6. 增加断点恢复；
7. 增加增量diff报告；
8. 建立包内相对路径；
9. 保留现有`fetch`和`run-and-validate`兼容；
10. 增加最终`validate-pack`命令。

## 10.2 验收

- JSON/Parquet/DuckDB/Excel均可读取；
- 表头和schema一致；
- Excel多列导出回归不复发；
- 包移动后证据路径仍有效；
- 重新运行只处理变化项；
- 文档：
  - `70_W07_exports_cli_plan.md`；
  - `71_W07_exports_cli_result.md`。

## 11. W08：全量E2E、兼容和性能

## 11.1 样本矩阵

| 样本 | 目的 |
|---|---|
| 688521 | 科创板、复杂PDF、当前金标准 |
| 002352 | 深市/CNINFO、A+H及资本事项回归 |
| 更正报告样本 | 版本链和as-of-date |
| 明确零样本 | FACT_ZERO_EXPLICIT |
| 非金融/制造样本 | 存货、产能、分部章节 |
| 北交所样本 | 明确部分完成和来源不可用状态 |

## 11.2 验收批次

1. 单元测试；
2. parser fixtures；
3. 688521 thin-slice；
4. 002352 thin-slice；
5. 688521 research-full；
6. 多样本批量；
7. 重复运行缓存测试；
8. as-of-date回放；
9. 包移动和重新导入；
10. 性能和资源报告。

## 11.3 兼容性

- 原F10输出字段和命令不破坏；
- 原cross-validation输出保留或提供迁移说明；
- Raw Pack旧调用仍可工作；
- 任何废弃项至少经过一个版本的warning期。

## 12. W09：UI/API对接

在数据契约稳定后：

- UI展示覆盖与准确率的不同维度；
- 可筛选可疑解析、来源冲突和未解决项；
- 点击事实进入原文证据；
- 展示as-of-date和版本链；
- 支持选择thin-slice/research-full；
- 与PR #16协调，避免并行修改同一执行控制文件。

## 13. 每阶段必须新增的Markdown

```text
docs/plans/f10-research-mapping-evidence-pack-v1/
├── 00_task_contract.md
├── 01_baseline_audit_688521.md
├── 02_target_architecture.md
├── 03_implementation_plan.md
├── 04_acceptance_matrix.md
├── 10_W01_parser_correctness_plan.md
├── 11_W01_parser_correctness_result.md
├── 20_W02_point_in_time_plan.md
├── 21_W02_point_in_time_result.md
├── 30_W03_reconciliation_metrics_plan.md
├── 31_W03_reconciliation_metrics_result.md
├── 40_W04_ontology_mapping_plan.md
├── 41_W04_ontology_mapping_result.md
├── 50_W05_evidence_graph_plan.md
├── 51_W05_evidence_graph_result.md
├── 60_W06_section_parsers_plan.md
├── 61_W06_section_parsers_result.md
├── 70_W07_exports_cli_plan.md
├── 71_W07_exports_cli_result.md
├── 80_W08_e2e_plan.md
├── 81_W08_e2e_result.md
└── 99_final_review.md
```

代码执行不会因提交文档而中断；文档提交是检查点的一部分。

## 14. 提交和PR策略

1. 本规划分支仅包含Markdown；
2. 规划确认后：
   - 若PR #18已合并，基于最新main创建实现分支；
   - 若PR #18未合并且修改面重叠，先等待其确定接口或只做不重叠的parser fixture工作；
3. 每个W工作包至少一个独立提交；
4. 大工作包使用Draft PR持续展示；
5. 不把临时探针、生成数据或大文件提交到main；
6. 阶段输出通过Actions artifact或测试fixture管理；
7. 最终合并前执行完整回归矩阵。

## 15. 建议执行顺序

```text
W01解析正确性
-> W02时点/版本
-> W03对账与指标
-> W04研究本体/规范事实
-> W05统一证据图
-> W06章节解析器
-> W07导出/CLI/恢复
-> W08全量E2E
-> W09 UI/API
```

这是关键路径。P0正确性未通过前，不扩大官方字段覆盖，也不以当前“0冲突”作为生产级准确性的证明。
