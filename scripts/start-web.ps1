$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Invoke-Checked {
    param([Parameter(Mandatory = $true)][string[]]$Command)
    $Program = $Command[0]
    $Arguments = if ($Command.Count -gt 1) { $Command[1..($Command.Count - 1)] } else { @() }
    Write-Host ">> $Program $($Arguments -join ' ')" -ForegroundColor Cyan
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program $($Arguments -join ' ')" }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $PythonBootstrap = "py" }
    else { throw "未找到Python。请安装Python 3.12并勾选Add Python to PATH。" }
} else {
    $PythonBootstrap = "python"
}

if (-not (Test-Path ".venv")) {
    if ($PythonBootstrap -eq "py") { Invoke-Checked -Command @("py", "-3.12", "-m", "venv", ".venv") }
    else { Invoke-Checked -Command @("python", "-m", "venv", ".venv") }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Cli = Join-Path $Root ".venv\Scripts\ashare-f10.exe"
Invoke-Checked -Command @($Python, "-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked -Command @($Python, "-m", "pip", "install", "-e", ".")

$Url = "http://127.0.0.1:8000/run.html"
Write-Host "正在启动A股F10可视化执行中心：$Url" -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process '$Url'"
) | Out-Null

& $Cli serve --host 127.0.0.1 --port 8000
