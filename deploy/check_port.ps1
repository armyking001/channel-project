# Check what is running on 172.16.10.92
# Usage: pwsh -File check_port.ps1
param([string]$ServerIP = "172.16.10.92", [string]$User = "admin001")

$securePwd = Read-Host "Enter password for $User@$ServerIP" -AsSecureString
$PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
)

$env:SSHPASS = $PlainPassword

$cmd = @'
echo '=== ALL LISTENING PORTS ==='
ss -tlnp 2>&1 | head -30
echo ''
echo '=== SERVICES ==='
systemctl list-units --type=service --state=running --no-pager 2>&1 | head -30
echo ''
echo '=== DEPLOY DIR EXISTS? ==='
ls -la /opt/channel-project 2>&1 | head -5
echo ''
echo '=== NGINX CONFIG ==='
ls /etc/nginx/sites-enabled/ 2>&1
echo ''
echo '=== PORT 26731 ==='
ss -tlnp | grep 26731 || netstat -tlnp 2>&1 | grep 26731
echo ''
echo '=== WHICH PROCESS ON 26731 ==='
lsof -i :26731 2>&1 || ss -tlnp | grep 26731
'@

sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -tt "${User}@${ServerIP}" $cmd
Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue