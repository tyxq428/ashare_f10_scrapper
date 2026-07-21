# A股 F10 投研平台（ashare_f10_scrapper）

一套可本地运行、可通过 GitHub Actions 远程运行的 A 股 F10 数据平台。输入六位股票代码后，程序使用固定、版本化的东方财富 F10 接口清单，完成请求去重、日期和字段合并、分页、回退、缓存、断点恢复、标准化、搜索数据库、TTM、公式计算及 JSON/Excel/Parquet/DuckDB 导出。

> 当前首版固定使用已经验证过的接口范围，不自动发现或增加新接口。

## 主要能力

- 输入 `688521` 之类的六位代码，自动转换为不同接口需要的 `688521.SH`、`SH688521`、`1.688521` 等格式。
- 固定接口清单共 113 个请求组（包含页面汇总及公告/研报正文动态任务）。
- 同类接口合并字段、报告期和分页；失败时按原请求形态精确回退。
- 跨接口并行、接口内分页并行、公告和研报正文并行。
- 原始响应 gzip 缓存，重复运行跳过成功请求。
- 输出：
  - 完整 JSON
  - Excel
  - Parquet 事实表
  - DuckDB 投研数据库
- 网页：
  - 任务进度
  - 公司总览
  - 中文名 / 原始 Key / 区块 / 时间 / 数值范围模糊搜索
  - 自定义结束期 TTM
  - 任意字段安全公式计算
  - 来源追溯和文件下载
- GitHub Pages 静态查看器支持上传已生成 JSON 后浏览和搜索。

## 一分钟启动

### Docker（推荐）

```bash
git clone https://github.com/tyxq428/ashare_f10_scrapper.git
cd ashare_f10_scrapper
docker compose up --build
```

打开：`http://localhost:8000`

### Windows 原生运行

PowerShell：

```powershell
.\scripts\start.ps1
```

或者双击 / 执行：

```bat
scripts\start.bat
```

### Linux / macOS 原生运行

```bash
./scripts/start.sh
```

## 命令行

```bash
# 安装
python -m pip install -e .

# 拉取并生成全部文件
ashare-f10 fetch 688521

# 指定输出目录和并发
ashare-f10 fetch 688521 --output ./data/688521/test --workers 8

# 强制忽略已有检查点
ashare-f10 fetch 688521 --force

# 验证运行目录
ashare-f10 validate ./data/688521/manual

# 启动网页
ashare-f10 serve --host 127.0.0.1 --port 8000
```

## GitHub Actions 远程运行

1. 打开仓库 `Actions`。
2. 选择 **Fetch A-share F10**。
3. 点击 **Run workflow**。
4. 输入六位代码和并发数。
5. 运行结束后下载 Artifact。

Artifact 包含原始缓存、标准化数据库、JSON 和 Excel。Actions 和本地版本调用的是同一 Python 内核。

## GitHub Pages

工作流 **Deploy static viewer to Pages** 会部署静态查看器。由于 GitHub Pages 不能运行 Python，它只用于：

- 上传本地或 Actions 生成的 JSON；
- 在浏览器内浏览和搜索；
- 展示静态页面。

私有仓库中的网页若要安全地直接触发 Actions，需要第二阶段部署 Cloudflare Worker 或自有服务器，避免把 GitHub Token 暴露给浏览器。

## 数据目录

```text
data/<股票代码>/<job_id>/
├── raw/                   # 每个请求的gzip缓存
├── groups/                # 请求组结构化结果
├── normalized/
│   ├── facts.parquet
│   └── f10.duckdb
├── exports/
│   ├── <code>_F10_full.json
│   └── <code>_F10_full.xlsx
├── combined.json
├── checkpoint.json
└── artifacts.json
```

每只股票的最近一次完成任务通过：

```text
data/<股票代码>/latest.json
```

定位。

## 搜索数据模型

DuckDB 中的 `facts` 为长表结构：

| 字段 | 含义 |
|---|---|
| `security_code` | 股票代码 |
| `theme` | 页面主题 |
| `family` | 接口家族 |
| `dataset` | 数据集 |
| `report_date` | 报告期 |
| `event_date` | 事件日期 |
| `period_type` | Q1/Q2/Q3/FY/事件 |
| `data_semantics` | 流量、时点或事件 |
| `field_key` | 原始 Key |
| `field_name_cn` | 中文项目名称 |
| `value_num` | 数值值 |
| `value_text` | 文本值 |
| `unit` | 单位 |
| `source_url` | 来源 URL |

## TTM 口径

优先使用独立单季度数据：

```text
TTM = 最近连续四个独立季度之和
```

例如：

```text
2026Q1 TTM = 2025Q2单季 + 2025Q3单季 + 2025Q4单季 + 2026Q1单季
```

独立季度不足时使用累计口径：

```text
2026Q1 TTM = 2025FY - 2025Q1累计 + 2026Q1累计
```

资产负债表是时点值，不执行 TTM。

## 公式实验室

支持原始 Key：

```text
CIP / TOTAL_ASSETS
```

支持中文名称：

```text
F("在建工程") / F("资产总计")
```

支持函数：

```text
TTM("TOTAL_OPERATE_INCOME")
YOY("PARENT_NETPROFIT")
QOQ("INVENTORY")
AVG("TOTAL_ASSETS", 2)
CAGR("TOTAL_OPERATE_INCOME", 3)
```

可以组合：

```text
TTM("NETCASH_OPERATE") / TTM("PARENT_NETPROFIT")
TTM("TOTAL_OPERATE_INCOME") / AVG("TOTAL_ASSETS", 2)
```

公式使用 AST 白名单解析器，不执行任意 Python 或 JavaScript。

## 配置

复制 `.env.example` 为 `.env`：

```env
ASHARE_F10_DATA_DIR=./data
ASHARE_F10_MAX_WORKERS=8
ASHARE_F10_PAGE_WORKERS=4
ASHARE_F10_TIMEOUT=45
ASHARE_F10_RETRIES=3
ASHARE_F10_CACHE_TTL_HOURS=24
ASHARE_F10_HOST=127.0.0.1
ASHARE_F10_PORT=8000
```

遇到 429/403 可降低并发数。

## API

服务启动后访问：

- Swagger：`http://localhost:8000/docs`
- 健康检查：`GET /api/health`
- 创建任务：`POST /api/jobs`
- 查看任务：`GET /api/jobs/{job_id}`
- 搜索：`GET /api/stocks/{code}/search`
- 字段：`GET /api/stocks/{code}/fields`
- 报告期：`GET /api/stocks/{code}/periods`
- TTM：`POST /api/stocks/{code}/ttm`
- 公式：`POST /api/stocks/{code}/formula`

创建任务示例：

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"stock_code":"688521","resume":true}'
```

## 测试

```bash
python -m pip install -e ".[dev]"
ruff check src tests
pytest --cov=ashare_f10
```

## 已知边界

- 接口为公开网页内部接口，结构可能变化；失败会进入明确状态，不会猜测补数。
- 研报正文 ID 来自 PageAjax 页面汇总，公告正文 ID 来自公告列表。
- GitHub Pages 本身不能执行 Python，也不能安全保存 GitHub Token。
- 北京交易所市场参数已支持常见格式，但建议首次使用新市场股票时检查返回证券代码。
- 高频批量运行可能触发目标站点限速，应使用缓存并控制并发。

## Cloudflare / 服务器第二阶段

`deploy/cloudflare-worker/README.md` 列出了远程网页安全触发私有 Actions 所需的 Secrets。服务器部署可直接使用 `deploy/server/docker-compose.yml`，无需重写数据内核。

## 双源全字段自动交叉验证

网页默认采用一次输入模式：输入六位股票代码后，系统完成东方财富固定接口拉取、免费官方报告发现、官方事实解析、字段验证分类和双源对账。

```bash
ashare-f10 run-and-validate 688521 --max-periods 2
```

输出包括东方财富、官方披露和双源比较三套 JSON、Excel、Parquet、DuckDB，以及带PDF页码和原始行的证据包。官方报告未披露的东方财富字段会标记为 `NOT_IN_OFFICIAL_SCOPE`、`SOURCE_SPECIFIC` 或 `FUTURE_FREE_SOURCE_REQUIRED`，不会误判为数值冲突。
