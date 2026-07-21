# 免费官方数据交叉验证

本模块用**免费且官方**的披露文件验证东方财富 F10 数据，不接入 Wind、Choice 商业终端、iFinD、CSMAR、RESSET、聚源或其他收费数据源。

## 当前薄切片

首个自动化样本为 `688521`：

- 上交所正式披露的 2025 年年度报告；
- 上交所正式披露的 2026 年第一季度报告；
- 三张财务报表的关键项目；
- 资产负债表会计等式；
- 现金流量净增加额关系；
- 2026Q1 TTM 营业收入和归母净利润的双公式一致性。

验证器与东方财富抓取器只共享标准事实数据合同。官方报告发现、PDF 解析、报告版本识别和会计校验均使用独立代码。

## 命令行

```bash
ashare-f10 fetch 688521 --output data/688521/validation-run
ashare-f10 validate-official 688521 data/688521/validation-run \
  --annual-year 2025 \
  --quarter-year 2026
```

## 输出

运行目录下的 `validation/` 包含：

- `validation_summary.json`：验证范围、匹配率和验收状态；
- `validation_detail.parquet`：逐字段东方财富值与官方值；
- `official_facts.parquet`：从官方报告独立提取的事实；
- `validation_evidence.json`：报告、页码、原始行和计算证据；
- `validation_mismatches.xlsx`：差异、逻辑检查和 TTM 检查；
- `source_documents/`：官方 PDF 缓存；
- `source_hashes.json`：官方文件 SHA-256。

验证结果不会静默覆盖原始数据。发生冲突时，原值、官方值、报告页码和证据行均会保留。
