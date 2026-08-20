# ============================================================
# Channel Project Management System - One-Click Deploy
# Uploads local source as tar.gz, then runs upgrade on server
# ============================================================
param(
    [Parameter(Mandatory=$false)]
    [string]$ServerIP = "172.16.10.92",

    [Parameter(Mandatory=$false)]
    [string]$SSHUser = "admin001",

    [Parameter(Mandatory=$false)]
    [int]$SSHPort = 22,

    [Parameter(Mandatory=$false)]
    [string]$SSHKeyPath = "",

    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = ""  # Auto-detect if empty
)

# Color functions
function Write-Info($msg)  { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# Auto-detect project root
if ([string]::IsNullOrEmpty($ProjectRoot)) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $ProjectRoot = Split-Path -Parent $ScriptDir
}
Write-Info "Project root: $ProjectRoot"

$DeployScript = Join-Path $PSScriptRoot "upgrade_to_server.sh"
if (-not (Test-Path $DeployScript)) {
    Write-Err "Deploy script not found: $DeployScript"
}

# Check tools
$sshCmd = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $sshCmd) { Write-Err "ssh not found" }
$scpCmd = Get-Command scp -ErrorAction SilentlyContinue
if (-not $scpCmd) { Write-Err "scp not found" }
$sshpassCmd = Get-Command sshpass -ErrorAction SilentlyContinue

# Collect auth
if (-not [string]::IsNullOrEmpty($SSHKeyPath)) {
    if (-not (Test-Path $SSHKeyPath)) { Write-Err "SSH key not found: $SSHKeyPath" }
} else {
    if (-not $sshpassCmd) {
        Write-Warn "sshpass not found, recommend using SSH key"
        $useKey = Read-Host "Use SSH key? (y/n)"
        if ($useKey -eq "y") {
            $SSHKeyPath = Read-Host "SSH key path"
        } else {
            Write-Err "Install sshpass or configure SSH key"
        }
    } else {
        $cred = Get-Credential -UserName $SSHUser -Message "Password for $SSHUser@$ServerIP"
        if (-not $cred) { Write-Err "No credentials" }
        $PlainPassword = $cred.GetNetworkCredential().Password
    }
}

# SSH options
$BaseSSHOpts = @(
    "-P", $SSHPort,
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=NUL",
    "-o", "LogLevel=ERROR"
)

# ========== Step 1: Package local project ==========
Write-Info "Step 1: Packaging local project (Python script for proper Unicode)..."

$PackageScript = Join-Path $PSScriptRoot "package.py"
$TempTar = ""

# Try Python packaging first (handles Chinese paths correctly)
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd -and (Test-Path $PackageScript)) {
    Write-Info "Using Python script package.py..."
    $output = & python $PackageScript 2>&1
    Write-Host $output
    # Extract tar path from output
    $TempTarLine = $output | Where-Object { $_ -match 'Tarball: ' -and $_ -match '\.tar\.gz' } | Select-Object -Last 1
    if ($TempTarLine -match 'Tarball: (.+\.tar\.gz)') {
        $TempTar = $matches[1].Trim()
    }
    if (-not $TempTar -or -not (Test-Path $TempTar)) {
        Write-Warn "Python packaging failed, falling back to tar..."
        $TempTar = ""
    }
}

# Fallback: use tar (may include heavy files)
if ([string]::IsNullOrEmpty($TempTar)) {
    Write-Warn "Using tar fallback (may include node_modules/.venv)..."
    $TempTar = Join-Path $env:TEMP "channel-project-$(Get-Date -Format 'yyyyMMddHHmmss').tar.gz"
    $ParentDir = Split-Path -Parent $ProjectRoot
    $ProjectName = Split-Path -Leaf $ProjectRoot
    $CurDir = Get-Location
    Set-Location $ParentDir
    & tar -czf $TempTar $ProjectName 2>&1 | Out-Null
    Set-Location $CurDir
}

if (-not (Test-Path $TempTar)) {
    Write-Err "Failed to create package"
}

$TarSize = (Get-Item $TempTar).Length / 1MB
Write-Info "Package created: $TempTar ($([math]::Round($TarSize, 2)) MB)"

# ========== Step 2: Upload package and script ==========
Write-Info "Step 2: Uploading files to server..."
$RemoteTarPath = "/tmp/channel-project.tar.gz"
$RemoteScriptPath = "/tmp/upgrade_to_server.sh"

if ($SSHKeyPath) {
    & scp @BaseSSHOpts -i $SSHKeyPath $TempTar "${SSHUser}@${ServerIP}:${RemoteTarPath}"
    & scp @BaseSSHOpts -i $SSHKeyPath "$DeployScript" "${SSHUser}@${ServerIP}:${RemoteScriptPath}"
} else {
    & sshpass -p $PlainPassword scp @BaseSSHOpts $TempTar "${SSHUser}@${ServerIP}:${RemoteTarPath}"
    & sshpass -p $PlainPassword scp @BaseSSHOpts "$DeployScript" "${SSHUser}@${ServerIP}:${RemoteScriptPath}"
}

if ($LASTEXITCODE -ne 0) { Write-Err "Upload failed" }
Write-Info "Upload successful"

# Cleanup local temp file
Remove-Item $TempTar -Force -ErrorAction SilentlyContinue

# ========== Step 3: Check sudo ==========
Write-Info "Step 3: Checking sudo NOPASSWD..."
if ($SSHKeyPath) {
    $sudoCheck = & ssh @BaseSSHOpts -i $SSHKeyPath "${SSHUser}@${ServerIP}" "sudo -n true 2>&1; echo EXIT=\$?"
} else {
    $env:SSHPASS = $PlainPassword
    $sudoCheck = & sshpass -e ssh @BaseSSHOpts -o "SendEnv=SSHPASS" "${SSHUser}@${ServerIP}" "sudo -n true 2>&1; echo EXIT=\$?"
    Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue
}

if ($sudoCheck -match "EXIT=1") {
    Write-Warn "sudo requires password!"
    Write-Warn "Run on server: echo '$SSHUser ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/$SSHUser-nopasswd"
    $continue = Read-Host "Continue? (y/n)"
    if ($continue -ne "y") { exit 0 }
} else {
    Write-Info "sudo NOPASSWD OK"
}

# ========== Step 4: Run upgrade ==========
Write-Info "Step 4: Running upgrade on server..."
Write-Warn "This may take 5-10 minutes..."

if ($SSHKeyPath) {
    & ssh @BaseSSHOpts -i $SSHKeyPath "${SSHUser}@${ServerIP}" "chmod +x $RemoteScriptPath ; bash $RemoteScriptPath"
} else {
    $env:SSHPASS = $PlainPassword
    & sshpass -e ssh @BaseSSHOpts -o "SendEnv=SSHPASS" "${SSHUser}@${ServerIP}" "chmod +x $RemoteScriptPath ; bash $RemoteScriptPath"
    Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue
}

if ($LASTEXITCODE -ne 0) {
    Write-Err "Deployment failed, exit code: $LASTEXITCODE"
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  URL: http://$ServerIP:26731/admin/" -ForegroundColor White
Write-Host "  Default user: admin" -ForegroundColor White
Write-Host "  Default pass: admin123" -ForegroundColor White
Write-Host ""
Write-Host "  Change password after first login!" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan