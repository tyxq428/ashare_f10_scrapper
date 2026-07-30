[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RequestSource,

    [Parameter()]
    [ValidatePattern('^B\d{3}$')]
    [string]$BatchId = 'B001',

    [Parameter()]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$AsOfDate = '2026-07-30',

    [Parameter()]
    [ValidateRange(0, 500)]
    [int]$SmokeCount = 0,

    [Parameter()]
    [string]$DataRoot = 'data',

    [Parameter()]
    [string]$OutputRoot = '09_OUTPUTS\ascope-f10-local',

    [Parameter()]
    [ValidateRange(1, 2)]
    [int]$StockWorkers = 2,

    [Parameter()]
    [ValidateRange(1, 2)]
    [int]$MaxAttempts = 2,

    [Parameter()]
    [ValidateRange(60, 18000)]
    [int]$SoftDeadlineSeconds = 18000,

    [Parameter()]
    [ValidateRange(5, 300)]
    [int]$HeartbeatSeconds = 30,

    [Parameter()]
    [switch]$ForceRetry,

    [Parameter()]
    [switch]$FixtureMode,

    [Parameter()]
    [switch]$InspectOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing project virtual environment: $Python. Run: py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e '.[dev]'"
}

$ResolvedOutputRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $OutputRoot))
$ResolvedDataRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $DataRoot))
New-Item -ItemType Directory -Path $ResolvedOutputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $ResolvedDataRoot -Force | Out-Null

$SourcePath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $RequestSource))
if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Request source does not exist: $SourcePath"
}

if ($FixtureMode) {
    $FixtureRequest = Join-Path $ResolvedOutputRoot '_fixture_request'
    Remove-Item -LiteralPath $FixtureRequest -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path (Join-Path $FixtureRequest 'financial_batches') -Force | Out-Null

    $Manifest = Join-Path $SourcePath 'financial_request_manifest.json'
    $FixtureBatch = Join-Path $SourcePath 'B001_smoke_5.csv'
    if (-not (Test-Path -LiteralPath $Manifest) -or -not (Test-Path -LiteralPath $FixtureBatch)) {
        throw 'FixtureMode requires financial_request_manifest.json and B001_smoke_5.csv in RequestSource.'
    }
    Copy-Item -LiteralPath $Manifest -Destination (Join-Path $FixtureRequest 'financial_request_manifest.json') -Force
    Copy-Item -LiteralPath $FixtureBatch -Destination (Join-Path $FixtureRequest "financial_batches\$BatchId.csv") -Force
    Set-Content -LiteralPath (Join-Path $FixtureRequest 'INVESTMENT_USE_PROHIBITED') -Value 'FIXTURE_TEST_ONLY' -Encoding UTF8
    $SourcePath = $FixtureRequest
}

$BatchOutput = Join-Path $ResolvedOutputRoot $BatchId
$Checkpoint = Join-Path $BatchOutput 'checkpoint.json'

if ($InspectOnly) {
    if (-not (Test-Path -LiteralPath $Checkpoint)) {
        throw "Checkpoint does not exist: $Checkpoint"
    }
    & $Python -m ashare_f10.ascope_bridge.cli inspect-checkpoint $Checkpoint
    exit $LASTEXITCODE
}

$Arguments = @(
    '-m', 'ashare_f10.ascope_bridge.cli', 'run-batch', $SourcePath,
    '--batch-id', $BatchId,
    '--as-of-date', $AsOfDate,
    '--smoke-count', [string]$SmokeCount,
    '--data-root', $ResolvedDataRoot,
    '--output-root', $ResolvedOutputRoot,
    '--stock-workers', [string]$StockWorkers,
    '--max-attempts', [string]$MaxAttempts,
    '--soft-deadline-seconds', [string]$SoftDeadlineSeconds,
    '--heartbeat-seconds', [string]$HeartbeatSeconds
)
if ($ForceRetry) {
    $Arguments += '--force-retry'
}
if ($FixtureMode) {
    $Arguments += '--fixture-mode'
}

Write-Host '============================================================'
Write-Host 'A-SCOPE F10 batch export bridge'
Write-Host '============================================================'
Write-Host "Request source : $SourcePath"
Write-Host "Batch          : $BatchId"
Write-Host "Cutoff         : $AsOfDate"
Write-Host "Smoke count    : $SmokeCount"
Write-Host "Output         : $BatchOutput"
Write-Host "Fixture        : $($FixtureMode.IsPresent)"
Write-Host "Force retry    : $($ForceRetry.IsPresent)"
Write-Host ''

& $Python @Arguments
$ExitCode = $LASTEXITCODE

$ManifestPath = Join-Path $BatchOutput 'batch_manifest.json'
$ValidationPath = Join-Path $BatchOutput 'validation_report.json'
if (Test-Path -LiteralPath $ManifestPath) {
    Write-Host "Batch manifest : $ManifestPath"
}
if (Test-Path -LiteralPath $ValidationPath) {
    Write-Host "Validation     : $ValidationPath"
}
if (Test-Path -LiteralPath $Checkpoint) {
    Write-Host "Checkpoint     : $Checkpoint"
}

if ($ExitCode -ne 0) {
    Write-Error "A-SCOPE batch returned exit code $ExitCode. Completed securities and checkpoint were preserved."
}
exit $ExitCode
