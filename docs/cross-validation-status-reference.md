# 双源交叉验证状态与指标说明

本页解释网页、JSON、Excel、Parquet和DuckDB中使用的验证模式、对账状态和顶部指标。

## 一、验证模式（validation_mode）

验证模式回答的是：**这个东方财富字段理论上应该用什么方式验证？**

| 验证模式 | 中文含义 | 是否进入官方数值比较 |
|---|---|---|
| `OFFICIAL_DIRECT` | 官方定期报告或正式披露文件中直接存在的项目，例如资产总计、营业收入 | 是 |
| `OFFICIAL_DERIVED` | 使用官方基础事实重新计算的项目，例如TTM、财务比率、独立季度值 | 是 |
| `OFFICIAL_DOCUMENT_EVENT` | 通过正式公告验证的事件，例如分红、发行、股东大会、限售解禁 | 是，但通常是日期、文本或集合比较 |
| `OFFICIAL_METADATA` | 官方文件元数据，例如证券代码、报告期、报告类型、公告日期 | 是 |
| `NOT_IN_PERIODIC_REPORT_SCOPE` | 正常情况下不属于定期报告披露范围，例如实时行情 | 否 |
| `EASTMONEY_SOURCE_SPECIFIC` | 东方财富特有口径、排名、标签或平台计算 | 否 |
| `FUTURE_FREE_SOURCE_REQUIRED` | 定期报告中通常没有，但未来可以接入其他免费官方来源验证 | 暂不进入 |

验证模式是字段级分类，不代表本次任务已经取得官方值。

## 二、对账状态（status）

对账状态回答的是：**本条东方财富记录与本轮加载的官方事实比较后，结果是什么？**

### 已匹配状态

| 状态 | 含义 |
|---|---|
| `EXACT_MATCH` | 单位、期间和口径标准化后完全一致；数值绝对差不超过1元也按精确一致处理，以消除浮点尾差 |
| `WITHIN_ROUNDING` | 差异超过1元，但仍在官方报告显示单位和小数位对应的披露精度容差内 |
| `DERIVED_MATCH` | 东方财富指标与使用官方基础事实独立计算的结果一致 |
| `TEXT_MATCH_NORMALIZED` | 日期、证券代码、报告类型等文本标准化后一致 |
| `SET_MATCH` | 股东、人员、事件等集合比较后一致 |

### 真正冲突状态

以下状态会计入`true_conflict_count`：

| 状态 | 含义 |
|---|---|
| `MISMATCH` | 相同报告期、单位和范围下，数值差异超过容差 |
| `VERSION_CONFLICT` | 使用了不同版本的报告，例如原版与更正版 |
| `SCOPE_CONFLICT` | 合并报表与母公司报表范围混用 |
| `PERIOD_CONFLICT` | 年度累计、季度累计和独立单季度口径混用 |
| `UNIT_CONFLICT` | 元、千元、万元、亿元或百分比等单位无法统一 |

### 覆盖缺口状态

这些状态不是“数据冲突”：

| 状态 | 含义 |
|---|---|
| `MISSING_OFFICIAL` | 本字段理论上应由官方数据验证，且报告期已经加载，但当前解析事实集中没有找到可比项目；可能是官方未直接披露，也可能是解析覆盖仍需扩展 |
| `MISSING_EASTMONEY` | 官方文件中存在事实，但东方财富标准事实表中没有对应记录 |
| `OFFICIAL_PERIOD_NOT_LOADED` | 该历史报告期的官方PDF本轮没有加载；不参与一致性判断 |
| `OFFICIAL_SOURCE_UNAVAILABLE` | 当前市场的免费官方来源适配器尚未接入或暂不可用 |
| `NOT_IN_OFFICIAL_SCOPE` | 该字段不属于定期报告验证范围 |
| `SOURCE_SPECIFIC` | 东方财富特有字段，官方报告不存在同口径项目 |
| `FUTURE_FREE_SOURCE_REQUIRED` | 需要后续接入其他免费官方来源 |
| `UNRESOLVED` | 现有规则无法可靠判断，不能使用推测值补齐 |

## 三、顶部指标

### 东方财富事实

标准化后的东方财富事实记录数。它按接口、数据集、记录和字段展开，因此同一个财务项目可能在多个接口家族中重复出现。

### 官方事实

从本轮下载的官方报告中直接提取，加上使用官方基础事实计算得到的派生事实数量。

### 理论可比记录（comparable_count）

排除以下状态后的东方财富记录数：

- `NOT_IN_OFFICIAL_SCOPE`
- `SOURCE_SPECIFIC`
- `FUTURE_FREE_SOURCE_REQUIRED`
- `OFFICIAL_PERIOD_NOT_LOADED`
- `OFFICIAL_SOURCE_UNAVAILABLE`

因此，理论可比记录仍包含：

- 已匹配记录；
- `MISSING_OFFICIAL`；
- `MISSING_EASTMONEY`；
- 真正冲突。

它表示“应该尝试比较的记录数”，不是“已经取得两边数值的记录数”。

### 已形成双源匹配（matched_count）

状态属于以下集合的记录数：

- `EXACT_MATCH`
- `WITHIN_ROUNDING`
- `DERIVED_MATCH`
- `TEXT_MATCH_NORMALIZED`
- `SET_MATCH`

### 688521示例

某次688521任务中：

```text
理论可比记录：44,009
已形成双源匹配：548
MISSING_OFFICIAL：43,443
MISSING_EASTMONEY：18
真正冲突：0
```

关系为：

```text
44,009 = 548 + 43,443 + 18 + 0
```

差额很大的主要原因：

1. 东方财富事实是记录级长表，同一字段会在财务主表、主要指标、比率、杜邦等多个接口中重复出现；
2. 本轮只加载最近两个官方报告期，而官方解析器生成的是去重后的规范事实；
3. 大量理论上可验证的字段尚未在PDF解析目标中覆盖，状态为`MISSING_OFFICIAL`；
4. 匹配率是“记录级官方提取覆盖率”，不是数据准确率评分。

判断准确性时应优先看：

- `true_conflict_count`；
- `MISMATCH`及口径冲突；
- 会计逻辑检查；
- TTM双公式检查；
- 具体字段的PDF页码和原始行证据。

## 四、验收状态

| 验收状态 | 含义 |
|---|---|
| `PASS` | 分类完整、没有真实冲突，也没有未解决覆盖缺口 |
| `PASS_WITH_COVERAGE_GAPS` | 已纳入比较的事实没有真实冲突，但仍存在未加载报告期、未提取项目或来源专有字段 |
| `PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE` | 东方财富任务完成，但当前市场没有可用官方适配器；不能解释为双源验证通过 |
| `FAIL_SOURCE_CONFLICT` | 存在真实来源冲突 |
| `FAIL_CLASSIFICATION_COVERAGE` | 有字段没有验证模式 |

`PASS_WITH_COVERAGE_GAPS`表示当前已验证部分通过，不表示所有东方财富字段都已被官方报告覆盖。
