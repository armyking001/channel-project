#!/bin/bash
# Don't use set -e, allow individual steps to fail

echo "=== Stopping service ==="
sudo systemctl stop channel-project 2>/dev/null || true
sudo fuser -k 8000/tcp 2>/dev/null || true
sleep 3
echo "DONE"

echo "=== Backup and remove old ==="
if [ -d /opt/channel-project ]; then
    sudo mv /opt/channel-project /opt/channel-project-backup-$(date +%Y%m%d%H%M%S) || true
fi
sudo rm -rf /opt/channel-project
sudo mkdir -p /opt/channel-project/backend/static
echo "DONE"

echo "=== Extract new code ==="
cd /opt/channel-project
sudo tar -xzf /tmp/channel-project.tar.gz
ls | head -10
echo "EXTRACT DONE"

echo "=== Install frontend deps + build ==="
cd /opt/channel-project/frontend
sudo npm install 2>&1 | tail -3
sudo npm run build 2>&1 | tail -5
ls /opt/channel-project/backend/static/
echo "BUILD DONE"

echo "=== Verify python deps ==="
sudo python3 -c "import fastapi, uvicorn, sqlalchemy, pydantic, pydantic_settings, jose, passlib, multipart, openpyxl, docx, requests; import webdav3; print('OK ALL DEPS')" || echo "DEPS MISSING"

echo "=== Start service ==="
sudo systemctl start channel-project
sleep 5
sudo systemctl status channel-project --no-pager -n 5
echo "STATUS DONE"

echo "=== Test access ==="
curl -s -o /dev/null -w "ADMIN=%{http_code}\n" http://127.0.0.1:8000/admin/
echo "TEST DONE"
echo "=== ALL DONE ==="