# ============================================================
# 渠道项目登记系统 - 一键部署脚本（Windows 本地执行）
# ============================================================
# 用法:
#   1. 编辑下面的配置：SSH_USER, SSH_PASSWORD, SERVER_IP
#   2. 在 PowerShell 中执行: .\deploy_windows.ps1
# ============================================================

param(
    [string]$ServerIP = "172.16.10.92",
    [string]$SSHUser = "root",
    [string]$SSHPassword = "",
    [int]$SSHPort = 22
)

# ---------- 颜色 ----------
function Write-Info($msg)  { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# ---------- 配置 ----------
$SCRIPT_PATH = Join-Path $PSScriptRoot "deploy_to_server.sh"
$DEPLOY_DIR_REMOTE = "/opt/channel-project"

if (-not (Test-Path $SCRIPT_PATH)) {
    Write-Err "找不到部署脚本: $SCRIPT_PATH"
}

# ---------- 1. 检查 sshpass / plink ----------
Write-Info "检查 SSH 客户端..."
$sshClient = $null
if (Get-Command sshpass -ErrorAction SilentlyContinue) {
    $sshClient = "sshpass"
} elseif (Get-Command plink -ErrorAction SilentlyContinue) {
    $sshClient = "plink"
} else {
    Write-Err "请安装 sshpass 或 plink（PuTTY）"
}

# ---------- 2. 提示输入密码（如果没传）----------
if ([string]::IsNullOrEmpty($SSHPassword)) {
    $securePwd = Read-Host "请输入服务器 [$ServerIP] 的 $SSHUser 密码" -AsSecureString
    $SSHPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
    )
}

if ([string]::IsNullOrEmpty($SSHPassword)) {
    Write-Err "密码不能为空"
}

# ---------- 3. 上传脚本到服务器 ----------
Write-Info "上传部署脚本到服务器..."

# 优先用 scp + sshpass
if ($sshClient -eq "sshpass") {
    sshpass -p "$SSHPassword" scp -P $SSHPort "$SCRIPT_PATH" "${SSHUser}@${ServerIP}:/tmp/deploy_to_server.sh"
    if ($LASTEXITCODE -ne 0) { Write-Err "脚本上传失败" }

    Write-Info "开始远程部署..."
    sshpass -p "$SSHPassword" ssh -p $SSHPort -o StrictHostKeyChecking=no "${SSHUser}@${ServerIP}" "chmod +x /tmp/deploy_to_server.sh && bash /tmp/deploy_to_server.sh"
} elseif ($sshClient -eq "plink") {
    Write-Info "使用 plink 进行部署..."
    # 使用 plink 上传
    $env:PLINK_PROTOCOL = "ssh"
    & plink -P $SSHPort -pw $SSHPassword "${SSHUser}@${ServerIP}" "mkdir -p /tmp" 2>&1 | Out-Null
    & pscp -P $SSHPort -pw $SSHPassword "$SCRIPT_PATH" "${SSHUser}@${ServerIP}:/tmp/deploy_to_server.sh"
    if ($LASTEXITCODE -ne 0) { Write-Err "脚本上传失败" }
    & plink -P $SSHPort -pw $SSHPassword "${SSHUser}@${ServerIP}" "chmod +x /tmp/deploy_to_server.sh && bash /tmp/deploy_to_server.sh"
}

if ($LASTEXITCODE -ne 0) {
    Write-Err "部署失败，请检查服务器连接和密码"
}

Write-Info "✅ 部署完成！"
Write-Info "访问地址: http://$ServerIP/admin/"
Write-Info "默认账号: admin / admin123"