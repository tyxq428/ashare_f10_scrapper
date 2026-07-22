# W02：全历史官方验证后端集成

## 目标

让可视化任务使用已经通过688521全历史验证的`run_full_cross_validation`，不再要求用户提供具体年份。

## 设计

### 官方验证范围

| 范围ID | 用户文案 | `max_periods` |
|---|---|---:|
| `latest` | 最近2个报告期（快速） | 2 |
| `recent_3y` | 最近3年 | 12 |
| `recent_5y` | 最近5年 | 20 |
| `full_history` | 上市以来全部报告（推荐） | `None` |

后台从F10事实表自动获得报告期，并由证券生命周期模型自动识别上市日期、上市前期间、摘要报告和尚未披露期间。

### 兼容策略

- 保留旧请求中的`official_annual_year`和`official_quarter_year`字段，但标记为兼容字段，不再作为网页主流程参数。
- 新增`official_validation_scope`和派生值`official_max_periods`。
- 旧Sidecar可以继续读取。

### 状态策略

- `PASS`、`PASS_WITH_COVERAGE_GAPS`：`COMPLETED`。
- `FAIL_SOURCE_CONFLICT`或`manual_review_required=true`：`COMPLETED_WITH_REVIEW`，增加警告但不把任务标为程序失败。
- 代码异常、下载失败且无法恢复：`FAILED`。

### 进度

使用全历史Runner的progress callback，将`OFFICIAL_DISCOVERY`、`OFFICIAL_DOWNLOAD`、`OFFICIAL_PARSE`、`RECONCILIATION`、`EXPORT`转为中文阶段消息。

## 修改文件

- `src/ashare_f10/api/visual_execution.py`
- `src/ashare_f10/api/visual_jobs.py`
- `tests/test_visual_execution.py`

## 验收

- 默认范围为`full_history`；
- 不修改`cross_validation/runner.py`；
- 688521全历史Runner能够由可视化任务调用；
- 来源冲突被正确标记为需复核而非运行失败。
