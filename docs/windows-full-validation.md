# Windows本地运行、参数与分支安全指南

本指南适用于东方财富F10、免费官方披露双源验证及可选Raw Pack。

## 一、分支选择原则

### 稳定运行

正常使用应运行`main`分支。只有在工作目录干净时才执行自动更新：

```powershell
.\scripts\run_full_validation.ps1 -UpdateMain -StockCode 688521
```

`-UpdateMain`会依次执行：

```text
git fetch origin
git switch main
git pull --ff-only origin main
```

如果存在未提交修改，脚本会在切换分支前停止，不覆盖本地开发内容。

### 正在开发其他功能分支

不要在包含未完成开发代码的同一工作目录中使用`-UpdateMain`。有两种安全方式。

#### 方式A：直接使用当前开发分支

```powershell
.\scripts\run_full_validation.ps1 -StockCode 688521
```

脚本不会切换分支，也不会执行`git pull`，运行的就是当前分支代码。

#### 方式B：建立独立的只运行工作树

在原仓库目录执行：

```powershell
git fetch origin
git worktree add --detach ..\ashare_f10_run origin/main
Set-Location ..\ashare_f10_run
.\scripts\run_full_validation.ps1 -StockCode 688521
```

这种方式最适合同时开发Raw Pack或其他功能，不会影响原开发分支。

## 二、PowerShell脚本

### 最近两个官方报告期（推荐首次运行）

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 688521 `
  -Workers 8 `
  -MaxPeriods 2
```

### 指定输出目录

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 002352 `
  -OutputDir "D:\AshareData\002352" `
  -Workers 8 `
  -MaxPeriods 2
```

### 全部可发现官方报告期

`MaxPeriods=0`表示命令行不传`--max-periods`，程序尝试加载全部可发现报告期：

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 688521 `
  -MaxPeriods 0
```

### 忽略东方财富检查点重新抓取

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 688521 `
  -Force
```

### 同时生成Raw Pack

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 688521 `
  -MaxPeriods 2 `
  -IncludeRawPack `
  -RawPackPacks default `
  -RawPackMaxDocs 200
```

`RawPackPacks`可使用：

- `default`
- `all`
- 逗号分隔的pack_id

Raw Pack默认关闭，避免改变原有F10和双源验证行为。

### 完成后启动网页

```powershell
.\scripts\run_full_validation.ps1 `
  -StockCode 688521 `
  -SkipInstall `
  -StartWeb `
  -Port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

### 自动更新main并运行

只在干净的运行工作目录中使用：

```powershell
.\scripts\run_full_validation.ps1 `
  -UpdateMain `
  -StockCode 688521 `
  -Workers 8 `
  -MaxPeriods 2
```

## 三、BAT脚本

BAT是PowerShell脚本的包装器，参数完全相同。

```bat
scripts\run_full_validation.bat -StockCode 688521 -Workers 8 -MaxPeriods 2
```

全部报告期：

```bat
scripts\run_full_validation.bat -StockCode 688521 -MaxPeriods 0
```

带Raw Pack：

```bat
scripts\run_full_validation.bat -StockCode 688521 -IncludeRawPack -RawPackPacks all -RawPackMaxDocs 500
```

更新main后运行：

```bat
scripts\run_full_validation.bat -UpdateMain -StockCode 688521
```

## 四、脚本参数

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `StockCode` | `688521` | 六位A股代码 |
| `RepoDir` | 脚本所在仓库根目录 | 仓库路径 |
| `OutputDir` | `data/<代码>/manual-full-validation` | 输出目录 |
| `Workers` | `8` | 东方财富接口并发数 |
| `MaxPeriods` | `2` | 最近N个官方报告期；`0`表示全部 |
| `Force` | 关闭 | 忽略检查点重新拉取东方财富接口 |
| `IncludeRawPack` | 关闭 | 双源验证完成后生成Raw Pack |
| `RawPackPacks` | `default` | Raw Pack资料包选择 |
| `RawPackMaxDocs` | `200` | Raw Pack最多文档数 |
| `UpdateMain` | 关闭 | 工作树干净时切换并更新main |
| `SkipInstall` | 关闭 | 跳过pip安装，复用现有`.venv` |
| `StartWeb` | 关闭 | 完成后启动本地网页 |
| `Port` | `8000` | 网页端口 |

## 五、等价命令行

### 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 双源验证

```powershell
.\.venv\Scripts\python.exe -m ashare_f10.cli run-and-validate 688521 `
  --output data\688521\manual-full-validation `
  --workers 8 `
  --max-periods 2
```

### 全部官方报告期

省略`--max-periods`：

```powershell
.\.venv\Scripts\python.exe -m ashare_f10.cli run-and-validate 688521 `
  --output data\688521\all-periods `
  --workers 8
```

### 强制重新抓取

```powershell
.\.venv\Scripts\python.exe -m ashare_f10.cli run-and-validate 688521 `
  --output data\688521\forced `
  --workers 8 `
  --max-periods 2 `
  --force
```

### 验证输出结构

```powershell
.\.venv\Scripts\python.exe scripts\verify_full_cross_validation.py `
  data\688521\manual-full-validation
```

该验证会检查：

- JSON、Parquet、DuckDB和Excel存在且可打开；
- 字段分类覆盖率；
- 真正冲突；
- Excel多列表格没有坍缩到A列；
- FastAPI查询和下载接口。

### 从现有F10运行生成Raw Pack

```powershell
.\.venv\Scripts\python.exe -m ashare_f10.cli raw-pack 688521 `
  --run-dir data\688521\manual-full-validation `
  --packs default `
  --max-docs 200
```

### 启动网页

```powershell
.\.venv\Scripts\python.exe -m ashare_f10.cli serve `
  --host 127.0.0.1 `
  --port 8000
```

## 六、输出位置

双源验证输出位于：

```text
<OutputDir>/cross_validation/
```

主要文件：

```text
<代码>_eastmoney_full.json/xlsx
<代码>_eastmoney_facts.parquet
<代码>_eastmoney.duckdb

<代码>_official_full.json/xlsx
<代码>_official_facts.parquet
<代码>_official.duckdb

<代码>_cross_validation.json/xlsx/parquet/duckdb
<代码>_validation_evidence.zip
cross_validation_summary.json
```

状态和验证模式解释见：

```text
docs/cross-validation-status-reference.md
```
