#!/bin/bash
# Auto-deploy script - minimal user input needed
set -e

echo "================================================"
echo "Channel Project Auto Deploy (no questions asked)"
echo "================================================"

# 1. Stop existing
echo "[1/8] Stopping old service..."
sudo systemctl stop channel-project 2>/dev/null || true
sudo pkill -9 -f uvicorn 2>/dev/null || true
sudo pkill -9 -f "app.main" 2>/dev/null || true
sleep 3
echo "  Done"

# 2. Backup old
echo "[2/8] Backing up old deployment..."
if [ -d /opt/channel-project ]; then
    sudo mv /opt/channel-project /opt/channel-project-backup-$(date +%Y%m%d%H%M%S)
fi
sudo rm -rf /opt/channel-project
sudo mkdir -p /opt/channel-project
echo "  Done"

# 3. Extract new code
echo "[3/8] Extracting tarball..."
cd /opt/channel-project
if [ -f /tmp/channel-project.tar.gz ]; then
    sudo tar -xzf /tmp/channel-project.tar.gz
    echo "  Extracted $(ls /opt/channel-project/ | wc -l) items"
else
    echo "  ERROR: /tmp/channel-project.tar.gz not found!"
    exit 1
fi

# 4. Setup backend
echo "[4/8] Setting up backend..."
cd /opt/channel-project/backend
sudo rm -f data.db data.db.bak* 2>/dev/null || true
echo "  Done"

# 5. Install Python deps
echo "[5/8] Installing Python dependencies (this may take 2-3 min)..."
sudo pip3 install --break-system-packages -r requirements.txt 2>&1 | tail -3
echo "  Done"

# 6. Build frontend
echo "[6/8] Building frontend (this may take 3-5 min)..."
cd /opt/channel-project/frontend
sudo npm install 2>&1 | tail -3
sudo npm run build 2>&1 | tail -3
echo "  Done"

# 7. Copy frontend build
echo "[7/8] Copying frontend assets..."
sudo mkdir -p /opt/channel-project/backend/static
sudo cp -r /opt/channel-project/frontend/dist/* /opt/channel-project/backend/static/
echo "  Done"

# 8. Setup systemd and start
echo "[8/8] Creating systemd service and starting..."
sudo tee /etc/systemd/system/channel-project.service > /dev/null << 'EOF'
[Unit]
Description=Channel Project Management System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/channel-project/backend
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/channel-project.log
StandardError=append:/var/log/channel-project.err.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable channel-project
sudo systemctl start channel-project
sleep 5

echo ""
echo "================================================"
echo "DEPLOY RESULT"
echo "================================================"
sudo systemctl status channel-project --no-pager -n 8 | head -10
echo ""
echo "HTTP Test:"
curl -s -o /dev/null -w "  Admin page HTTP=%{http_code}\n" http://127.0.0.1:8000/admin/
echo ""
echo "Access URLs:"
echo "  Admin: http://172.16.10.92:26731/admin/"
echo "  Default account: admin / admin123"
echo "================================================"