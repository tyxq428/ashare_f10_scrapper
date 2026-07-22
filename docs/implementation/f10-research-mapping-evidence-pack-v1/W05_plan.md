# W05计划：统一Official Evidence Graph

## 目标

将Raw Pack文档、官方定期报告、官方事实、F10源事实、Canonical Observation和页级证据连接为统一可穿透证据图。

## 节点类型

```text
SECURITY
DOCUMENT
ATTACHMENT
PARSED_TEXT
EVIDENCE_LOCATION
SOURCE_FACT
CANONICAL_OBSERVATION
```

## 边类型

```text
DESCRIBES_SECURITY
SUPERSEDES
ATTACHED_TO
PARSED_FROM
DERIVED_FROM_DOCUMENT
LOCATED_AT
SELECTED_FOR
SUPPORTS
CONFLICTS_WITH
QUARANTINED_FOR
```

## 实施内容

1. 新增`evidence`包和稳定节点/边ID；
2. 统一`OfficialDocument`与Raw Pack `SourceDocument`字段；
3. 对只有URL、没有显式Document记录的源事实建立可审计placeholder文档节点；
4. 将页码、原始行、表格或文本范围建为Evidence Location；
5. 将W04 lineage转换成Observation→Source Fact边；
6. 将Source Fact连接到Document和Evidence Location；
7. 将文档版本连接成`SUPERSEDES`链；
8. 将Raw Pack附件和解析文本接入图；
9. 输出节点表、边表、证据覆盖统计和质量检查；
10. 提供从Observation追溯至原始证据的确定性查询函数。

## 薄切片

- 官方利润表事实→年度报告→PDF页码→原始行；
- 东方财富事实→接口URL placeholder文档；
- 更正版→原版；
- 多来源规范事实→多个支持证据；
- 解析可疑事实→QUARANTINED边；
- Raw Pack附件→父文档。

## 验收标准

- 节点和边ID稳定且无重复；
- 不存在悬空边；
- 每个Canonical Observation至少连接一条Source Fact；
- 有官方证据的规范事实可追溯到文档、页码和原始行；
- 文档SHA-256、URL和版本字段保留；
- 无证据不伪造Evidence Location；
- 单元测试和现有工作流通过。

## 恢复入口

```yaml
phase: W05
checkpoint: W05_PLAN_COMMITTED
next_action: implement_unified_evidence_graph
```
