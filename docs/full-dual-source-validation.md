# 全字段双源自动交叉验证

该功能使用一次股票代码输入，依次完成：

1. 东方财富固定接口全量拉取；
2. 免费官方披露文件发现与下载；
3. 官方事实独立解析；
4. 字段验证模式100%分类；
5. 双源对账、会计逻辑和TTM双公式检查；
6. JSON、Excel、Parquet、DuckDB和证据包导出。

执行前会检查仓库中的《通用高效率任务执行_标准化流程.md》，并按检查点、缓存、幂等、来源证据和四层验证规则运行。

## 本地运行

```bash
python -m pip install -e ".[dev]"
ashare-f10 run-and-validate 688521 --output data/688521/full-validation --workers 8 --max-periods 2
python scripts/verify_full_cross_validation.py data/688521/full-validation
```

`--max-periods`省略时验证可发现的全部报告期。首次使用建议先设为2完成薄切片，再扩大范围。

## GitHub Actions

进入仓库Actions，选择 **Full Dual-Source Cross Validation**，输入：

- `stock_code`：六位股票代码；
- `workers`：东方财富接口并发数；
- `max_periods`：最近N个官方报告期，填0表示全部；
- `force`：是否忽略已有东方财富检查点。

运行结束后下载Artifact。

## 标准输出

每个任务产生三套同结构产品：

```text
<code>_eastmoney_full.json/xlsx
<code>_eastmoney_facts.parquet
<code>_eastmoney.duckdb

<code>_official_full.json/xlsx
<code>_official_facts.parquet
<code>_official.duckdb

<code>_cross_validation.json/xlsx/parquet/duckdb
<code>_validation_evidence.zip
cross_validation_summary.json
```

## 对账状态

- `EXACT_MATCH`：两来源完全一致；
- `WITHIN_ROUNDING`：仅存在披露精度尾差；
- `DERIVED_MATCH`：官方基础事实计算后匹配；
- `TEXT_MATCH_NORMALIZED`：文本标准化后一致；
- `MISMATCH`：相同期间、口径和单位下数值不同；
- `MISSING_OFFICIAL`：理论上应由官方披露验证，但当前未提取；
- `MISSING_EASTMONEY`：官方存在、东方财富事实表未找到；
- `OFFICIAL_PERIOD_NOT_LOADED`：本批次未加载该官方报告期，不计入冲突；
- `NOT_IN_OFFICIAL_SCOPE`：不属于定期报告范围，不计入冲突；
- `SOURCE_SPECIFIC`：东方财富专有口径，不计入冲突；
- `FUTURE_FREE_SOURCE_REQUIRED`：需要后续免费来源验证。

只有 `MISMATCH`、`VERSION_CONFLICT`、`SCOPE_CONFLICT`、`PERIOD_CONFLICT` 和 `UNIT_CONFLICT` 计入真正来源冲突。

## 当前免费官方来源边界

- 上交所、科创板：使用上交所正式披露文件；
- 深交所主板、创业板：使用巨潮资讯网免费正式披露文件；
- 北交所：字段完成分类，但官方适配器仍待接入北交所公开披露来源；
- 不接入Wind、Choice商业终端、iFinD、CSMAR、RESSET、聚源或其他收费数据源。

如果官方适配器尚不可用，任务返回 `PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE`，可比和匹配指标显示为“—”，而不是错误显示为零匹配的通过状态。
