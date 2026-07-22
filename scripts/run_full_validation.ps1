param(
    [ValidatePattern('^\d{6}$')]
    [string]$StockCode = "688521",

    [string]$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$OutputDir = "",

    [ValidateRange(1, 64)]
    [int]$Workers = 8,

    [ValidateRange(0, 80)]
    [int]$MaxPeriods = 2,

    [switch]$Force,
    [switch]$IncludeRawPack,
    [string]$RawPackPacks = "default",

    [ValidateRange(1, 5000)]
    [int]$RawPackMaxDocs = 200,

    [switch]$UpdateMain,
    [switch]$SkipInstall,
    [switch]$StartWeb,

    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
}

$repo = (Resolve-Path $RepoDir).Path
Set-Location $repo

if (-not (Test-Path (Join-Path $repo ".git"))) {
    throw "Not a Git repository: $repo"
}

if ($UpdateMain) {
    $dirty = (& git status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read Git status."
    }
    if ($dirty) {
        throw "The working tree has uncommitted changes. Commit/stash them, or run without -UpdateMain. No branch was changed."
    }
    Invoke-Checked -FilePath "git" -Arguments @("fetch", "origin")
    Invoke-Checked -FilePath "git" -Arguments @("switch", "main")
    Invoke-Checked -FilePath "git" -Arguments @("pull", "--ff-only", "origin", "main")
}
else {
    $branch = (& git branch --show-current).Trim()
    Write-Host "Using current branch: $branch" -ForegroundColor Cyan
    Write-Host "No branch switch or Git pull will be performed. Use -UpdateMain only in a clean run-only working tree." -ForegroundColor Yellow
}

$venvDir = Join-Path $repo ".venv"
$python = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $python)) {
    Invoke-Checked -FilePath "python" -Arguments @("-m", "venv", $venvDir)
}

if (-not $SkipInstall) {
    Invoke-Checked -FilePath $python -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    # Array arguments avoid Windows PowerShell treating '-e' as an abbreviated function parameter.
    Invoke-Checked -FilePath $python -Arguments @("-m", "pip", "install", "-e", ".[dev]")
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $repo ("data\{0}\manual-full-validation" -f $StockCode)
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $repo $OutputDir
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$runArgs = @(
    "-m", "ashare_f10.cli", "run-and-validate", $StockCode,
    "--output", $OutputDir,
    "--workers", [string]$Workers
)
if ($MaxPeriods -gt 0) {
    $runArgs += @("--max-periods", [string]$MaxPeriods)
}
if ($Force) {
    $runArgs += "--force"
}

Write-Host "Running dual-source validation for $StockCode" -ForegroundColor Cyan
Write-Host "Output: $OutputDir" -ForegroundColor Cyan
Invoke-Checked -FilePath $python -Arguments $runArgs
Invoke-Checked -FilePath $python -Arguments @("scripts\verify_full_cross_validation.py", $OutputDir)

if ($IncludeRawPack) {
    Write-Host "Generating optional Raw Pack..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $python -Arguments @(
        "-m", "ashare_f10.cli", "raw-pack", $StockCode,
        "--run-dir", $OutputDir,
        "--packs", $RawPackPacks,
        "--max-docs", [string]$RawPackMaxDocs
    )
}

if ($StartWeb) {
    Write-Host "Starting Web UI at http://127.0.0.1:$Port" -ForegroundColor Green
    Start-Process -FilePath $python -ArgumentList @(
        "-m", "ashare_f10.cli", "serve",
        "--host", "127.0.0.1",
        "--port", [string]$Port
    ) -WorkingDirectory $repo
}

Write-Host "" 
Write-Host "Completed successfully." -ForegroundColor Green
Write-Host "Cross-validation files: $(Join-Path $OutputDir 'cross_validation')"
Write-Host "To inspect the Web UI later: .\scripts\run_full_validation.ps1 -StockCode $StockCode -SkipInstall -StartWeb"
