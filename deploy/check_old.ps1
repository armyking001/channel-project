# Diagnose old deployment on 172.16.10.92
param([string]$ServerIP = "172.16.10.92", [string]$User = "admin001")

$securePwd = Read-Host "Enter password for $User@$ServerIP" -AsSecureString
$PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
)

$env:SSHPASS = $PlainPassword

$cmd = @'
echo '=== PORT 26731 OWNER ==='
sudo lsof -i :26731 2>&1 || sudo ss -tlnp | grep 26731
echo ''
echo '=== EXISTING DEPLOY DIR ==='
sudo ls -la /opt/channel-project 2>&1 | head -20
echo ''
echo '=== OLD SERVICE ==='
sudo systemctl status channel-project --no-pager 2>&1 | head -20
echo ''
echo '=== NGINX CONFIG ==='
sudo ls /etc/nginx/sites-enabled/ 2>&1
echo ''
echo '=== NGINX CONF FILE ==='
sudo cat /etc/nginx/sites-enabled/* 2>&1 | head -80
echo ''
echo '=== DB USERS ==='
sudo sqlite3 /opt/channel-project/backend/data.db 'SELECT id, username, real_name, role FROM users' 2>&1
'@

sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -tt "${User}@${ServerIP}" $cmd
Remove-Item Env:SSHPASS -ErrorAction SilentlyContinue