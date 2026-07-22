# 双源交叉验证状态与指标说明

本页解释网页、JSON、Excel、Parquet和DuckDB中使用的验证模式、对账状态、证券生命周期状态和顶部指标。

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

### 覆盖缺口与生命周期状态

这些状态不是“两个来源已经比较后发现数值冲突”：

| 状态 | 含义 |
|---|---|
| `MISSING_OFFICIAL` | 本字段理论上应由官方数据验证，且报告期已经加载，但当前解析事实集中没有找到可比项目；可能是官方未直接披露，也可能是解析覆盖仍需扩展 |
| `MISSING_EASTMONEY` | 官方文件中存在事实，但东方财富标准事实表中没有对应记录 |
| `OFFICIAL_PERIOD_NOT_LOADED` | 该历史报告期的官方PDF本轮没有加载；不参与一致性判断 |
| `OFFICIAL_SOURCE_UNAVAILABLE` | 当前市场的免费官方来源适配器尚未接入或暂不可用 |
| `PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED` | 报告期早于该证券上市日期，同一上市代码不存在定期报告；应改用招股说明书或发行上市申报文件验证 |
| `OFFICIAL_REPORT_SUMMARY_SCOPE_GAP` | 官方文件已经发现并提取，但旧版报告只披露“主要财务数据”摘要，没有完整三张报表；摘要未披露项目不判为冲突 |
| `OFFICIAL_DOCUMENT_EXTRACTION_FAILED` | 官方完整报告已经发现和下载，但当前解析器没有提取到可比事实，需要修复解析器 |
| `POST_LISTING_OFFICIAL_REPORT_NOT_FOUND` | 证券已上市、该期间理论上应有报告，但官方查询没有发现文件，需要继续调查来源或版本 |
| `OFFICIAL_REPORT_NOT_YET_DISCLOSED` | 报告期已经出现在上游数据中，但截至任务运行时对应官方定期报告尚未披露 |
| `NOT_IN_OFFICIAL_SCOPE` | 该字段不属于定期报告验证范围 |
| `SOURCE_SPECIFIC` | 东方财富特有字段，官方报告不存在同口径项目 |
| `FUTURE_FREE_SOURCE_REQUIRED` | 需要后续接入其他免费官方来源 |
| `UNRESOLVED` | 现有规则无法可靠判断，不能使用推测值补齐 |

## 三、报告期生命周期表

比较数据库新增`report_period_lifecycle`表，按报告期记录：

- 证券代码和交易所；
- 上市日期及其来源；
- 报告期；
- `PRE_LISTING_PERIOD`、`LISTING_TRANSITION_PERIOD`、`POST_LISTING_PERIODIC_EXPECTED`或`POST_LISTING_PERIOD_NOT_YET_DISCLOSED`；
- 官方文件是否发现；
- 官方事实提取数量；
- 最终覆盖状态。

这张表用于区分“官方网站缺文件”“证券当时尚未上市”“报告尚未披露”和“文件存在但解析失败”。

## 四、顶部指标

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
- `PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED`
- `OFFICIAL_REPORT_SUMMARY_SCOPE_GAP`
- `OFFICIAL_REPORT_NOT_YET_DISCLOSED`

因此，理论可比记录仍包含：

- 已匹配记录；
- `MISSING_OFFICIAL`；
- `MISSING_EASTMONEY`；
- `OFFICIAL_DOCUMENT_EXTRACTION_FAILED`；
- `POST_LISTING_OFFICIAL_REPORT_NOT_FOUND`；
- 真正冲突。

它表示“应该尝试比较的记录数”，不是“已经取得两边数值的记录数”。

### 已形成双源匹配（matched_count）

状态属于以下集合的记录数：

- `EXACT_MATCH`
- `WITHIN_ROUNDING`
- `DERIVED_MATCH`
- `TEXT_MATCH_NORMALIZED`
- `SET_MATCH`

## 五、688521完整历史示例

完成生命周期修复后的688521全历史任务：

```text
上市日期：2020-08-18（SSE公司概况）
上市前报告期：9个
上市后官方报告发现缺口：0
旧版摘要式报告：2020Q3、2021Q1
尚未披露报告期：2026H1
官方直接及派生事实：2,975
已形成双源匹配：6,191
真正冲突：1
```

唯一保留冲突为：

```text
报告期：2020-12-31
字段：INVEST_PAY_CASH（投资支付的现金）
东方财富：0元
上交所2020年年度报告：53,000,000元
官方证据：年报第146页“投资支付的现金 53,000,000.00”
```

东方财富明确返回0、官方正式报告明确为非零，因此系统保留`MISMATCH`，不会为了让验收状态变成PASS而覆盖或隐藏来源差异。

判断准确性时应优先看：

- `true_conflict_count`；
- `MISMATCH`及口径冲突；
- 会计逻辑检查；
- TTM双公式检查；
- 具体字段的PDF页码和原始行证据；
- `report_period_lifecycle`中的报告期覆盖分类。

## 六、验收状态

| 验收状态 | 含义 |
|---|---|
| `PASS` | 分类完整、没有真实冲突，也没有未解决覆盖缺口 |
| `PASS_WITH_COVERAGE_GAPS` | 已纳入比较的事实没有真实冲突，但仍存在未加载报告期、未提取项目或来源专有字段 |
| `PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE` | 东方财富任务完成，但当前市场没有可用官方适配器；不能解释为双源验证通过 |
| `FAIL_SOURCE_CONFLICT` | 存在一个或多个有来源证据支持的真实差异；数据包仍然完整可用，但必须保留冲突并提示人工审阅 |
| `FAIL_CLASSIFICATION_COVERAGE` | 有字段没有验证模式 |

`PASS_WITH_COVERAGE_GAPS`表示当前已验证部分通过，不表示所有东方财富字段都已被官方报告覆盖。`FAIL_SOURCE_CONFLICT`也不等于任务执行失败：它表示系统成功发现并保留了真实来源差异。
