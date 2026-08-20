#!/bin/bash
# Fix the service to use system Python instead of venv
set -e

echo "[1/5] Stopping service..."
sudo systemctl stop channel-project 2>/dev/null || true
sudo pkill -9 -f "uvicorn.*app.main" 2>/dev/null || true
sleep 3

echo "[2/5] Checking python path..."
# Use system python directly (we already installed deps to system via --break-system-packages)
PYTHON_PATH=$(which python3)
echo "  System python: $PYTHON_PATH"

# Verify key modules are importable
sudo -u root $PYTHON_PATH -c "import fastapi, uvicorn, sqlalchemy, pydantic, jose, passlib; print('  All deps OK')"

echo "[3/5] Updating systemd service..."
sudo tee /etc/systemd/system/channel-project.service > /dev/null << EOF
[Unit]
Description=Channel Project Management System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/channel-project/backend
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$PYTHON_PATH -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/channel-project.log
StandardError=append:/var/log/channel-project.err.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "  Service updated"

echo "[4/5] Starting service..."
sudo systemctl start channel-project
sleep 5

echo "[5/5] Verifying..."
sudo systemctl status channel-project --no-pager -n 10 | head -8
echo ""
echo "HTTP Test:"
curl -s -o /dev/null -w "  /admin/ HTTP=%{http_code}\n" http://127.0.0.1:8000/admin/
curl -s -o /dev/null -w "  /       HTTP=%{http_code}\n" http://127.0.0.1:8000/
echo ""
echo "Access URL: http://172.16.10.92:26731/admin/"
echo "Default account: admin / admin123"
echo ""
echo "DONE"