# W09结果：Research Pack API、Web UI与最终消费契约

## 阶段结论

W09已完成。Research Pack已通过独立API路由、Web页面和CLI接入现有平台，并保持原F10、Raw Pack、Cross Validation和Visual Execution接口兼容。

## 实施成果

### API

新增`src/ashare_f10/api/research_pack.py`，主要接口包括：

```text
POST /api/research-pack/jobs
GET  /api/research-pack/jobs
GET  /api/research-pack/jobs/{job_id}
GET  /api/research-pack/stocks/{stock_code}/latest
POST /api/research-pack/stocks/{stock_code}/canonical/query
GET  /api/research-pack/stocks/{stock_code}/gaps
POST /api/research-pack/stocks/{stock_code}/evidence/trace
GET  /api/research-pack/stocks/{stock_code}/documents
GET  /api/research-pack/stocks/{stock_code}/download/{kind}
```

接口支持规范事实筛选、Coverage Gap、事实到官方文档和页码的证据穿透，以及JSON、Excel、DuckDB、Manifest、Quality和Checkpoint下载。

### Web UI

新增：

```text
src/ashare_f10/web/research-pack.html
src/ashare_f10/web/research-pack.css
src/ashare_f10/web/research-pack.js
```

页面支持：

- 股票代码、`as_of_date`和运行预设；
- `research-full`与`thin-slice`；
- 分类覆盖、比较覆盖、比较准确率、证据完整率和未解决率；
- Canonical Observation、状态、报告期和研究模块筛选；
- `PARSE_SUSPECT`、`SOURCE_CONFLICT`和`UNRESOLVED`查看；
- 文档版本链、`SUPERSEDES`关系和证据位置；
- 交付Artifact下载。

### CLI与运行预设

```bash
ashare-f10 research-pack 688521 <run_dir> --preset research-full --as-of-date 2026-07-22
ashare-f10 research-pack 688521 <run_dir> --preset thin-slice --as-of-date 2026-07-22
ashare-f10 validate-pack <research_pack_dir>
```

预设、截止日、数据文件哈希、本体、注册表和确定性提取器版本均进入输入指纹；重复运行可命中缓存，发生语义变化时自动重建。

## 主分支兼容处理

实施分支已与最新`main`完成语义同步，保留并兼容：

- 证券上市生命周期和报告期状态；
- SSE与CNINFO官方报告路径；
- Raw Pack；
- Visual Execution；
- resilient fetch和有限重试；
- 现有Web与API入口。

核心重叠文件采用语义合并，而非简单覆盖：

```text
cross_validation/comparator.py
cross_validation/models.py
cross_validation/runner.py
api/app_with_raw_pack.py
.github/workflows/test.yml
```

## 验收结果

- API回归测试通过；
- JavaScript语法检查通过；
- 编译、Ruff和全量Pytest通过；
- Research Pack W08 Matrix通过；
- 688521 E2E、官方验证和Raw Pack回归通过；
- 原F10、Raw Pack、Cross Validation和Visual Execution接口未被破坏；
- 分支与`main`可合并；
- 不需要人工介入。

## 恢复入口

```yaml
phase: W09
status: COMPLETED
last_successful_step: API_UI_main_sync_and_final_regression
next_action: merge_PR21
human_intervention_required: false
```
