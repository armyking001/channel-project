# Quick packaging using robocopy (Windows native, fast)
# Usage: pwsh -File package.ps1
param([string]$ProjectRoot = "z:\soft-RED\hermes\开发软件\渠道项目登记")

# Directories to EXCLUDE (will not be copied)
$ExcludeDirs = @(
    "deploy",
    "node_modules",
    ".venv",
    "__pycache__",
    ".git",
    "dist",
    "static",
    ".docx_lib",
    "channel_code"
)

# File patterns to EXCLUDE
$ExcludeFiles = @(
    "*.pyc",
    "*.bak",
    "*.log",
    "*.zip",
    "*.docx",
    "*.tar.gz",
    "*.tmp",
    "data.db",
    "data.db.bak*",
    "uvicorn.out.log",
    "uvicorn.err.log"
)

Write-Host "[INFO] Packaging project with robocopy..." -ForegroundColor Green
Write-Host "       Source: $ProjectRoot" -ForegroundColor Green

# Create staging dir
$TempDir = Join-Path $env:TEMP "channel-stage-$(Get-Date -Format 'yyyyMMddHHmmss')"
New-Item -ItemType Directory -Path $TempDir | Out-Null

# Build robocopy args
$xArgs = @()
foreach ($dir in $ExcludeDirs) {
    $xArgs += "/XD"
    $xArgs += "`"$dir`""
}
foreach ($pattern in $ExcludeFiles) {
    $xArgs += "/XF"
    $xArgs += "`"$pattern`""
}
$xArgs += @("/MIR", "/R:0", "/W:0", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP")

# Run robocopy
$ProjectPath = "`"$ProjectRoot`""
$TempPath = "`"$TempDir`""
$CmdArgs = @($ProjectPath, $TempPath) + $xArgs

Write-Host "[INFO] Running robocopy..." -ForegroundColor Green
$proc = Start-Process -FilePath "robocopy" -ArgumentList $CmdArgs -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ge 8) {
    Write-Host "[ERROR] robocopy failed with code $($proc.ExitCode)" -ForegroundColor Red
    exit 1
}

# Check size
$SrcSize = (Get-ChildItem $TempDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
$FileCount = (Get-ChildItem $TempDir -Recurse -File).Count
Write-Host "[INFO] Staged: $FileCount files, $([math]::Round($SrcSize, 2)) MB" -ForegroundColor Green

# Tar from staging dir
$TempTar = Join-Path $env:TEMP "channel-project-$(Get-Date -Format 'yyyyMMddHHmmss').tar.gz"
$CurDir = Get-Location
Set-Location $TempDir
& tar -czf $TempTar . 2>&1 | Out-Null
Set-Location $CurDir

$TarSize = (Get-Item $TempTar).Length / 1MB
Write-Host "[INFO] Tarball: $TempTar ($([math]::Round($TarSize, 2)) MB)" -ForegroundColor Green

# Cleanup staging
Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Ready to upload!" -ForegroundColor Cyan