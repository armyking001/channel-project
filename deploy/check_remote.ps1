# Check deployment status on remote server
# Usage: sshpass -p 'PASSWORD' pwsh -File check_remote.ps1

param([string]$ServerIP = "172.16.10.92", [string]$User = "admin001")

# Read password
$securePwd = Read-Host "Enter password for $User@$ServerIP" -AsSecureString
$PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
)

$env:SSHPASS = $PlainPassword

$cmd = @'
echo '=== DEPLOY DIR ==='
ls /opt/channel-project 2>&1
echo ''
echo '=== SERVICE STATUS ==='
systemctl status channel-project --no-pager 2>&1 | head -20
echo ''
echo '=== LISTENING PORTS ==='
ss -tlnp 2>&1 | grep -E ':(80|8000)' || netstat -tlnp 2>&1 | grep -E ':(80|8000)'
echo ''
echo '=== DB USERS ==='
sudo sqlite3 /opt/channel-project/backend/data.db 'SELECT id, username, real_name, role, is_active FROM users' 2>&1
echo ''
echo '=== PROJECT COUNT ==='
sudo sqlite3 /opt/channel-project/backend/data.db 'SELECT COUNT(*) FROM projects' 2>&1
echo ''
echo '=== PROCESSES ==='
ps -ef | grep -E 'uvicorn|nginx' | grep -v grep | head -10
'@

sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -tt "${User}@${ServerIP}" $cmd
Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue