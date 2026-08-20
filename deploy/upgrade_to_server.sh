#!/usr/bin/env bash
# ============================================================
# Channel Project Management System - Upgrade Script (Linux)
# Replace old deployment at /opt/channel-project
# Keep nginx config on port 26731 (just update backend address)
# Supports: Ubuntu/Debian (apt) and CentOS/RHEL (yum/dnf)
# ============================================================
set -e

# ---------- Colors ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- Detect sudo ----------
SUDO=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        error "This script needs root privileges. Run with: sudo bash $0"
    fi
fi

# ---------- Parameters ----------
DEPLOY_DIR="/opt/channel-project"
SERVICE_PORT=8000
SERVICE_NAME="channel-project"
DB_FILE="$DEPLOY_DIR/backend/data.db"
NGINX_PORT=26731
SERVICE_USER="www-data"
ADMIN_PASSWORD="admin123"
BACKUP_DIR="/opt/channel-project-backup-$(date +%Y%m%d%H%M%S)"

# ---------- 1. Check environment ----------
info "Checking OS..."
if [ "$(uname)" != "Linux" ]; then
    error "This script only runs on Linux"
fi

# Detect distro
. /etc/os-release 2>/dev/null || true
DISTRO="${ID:-unknown}"
info "Detected distro: $DISTRO (${VERSION:-})"

# ---------- 2. Backup existing deployment ----------
if [ -d "$DEPLOY_DIR" ]; then
    info "Backing up existing deployment to $BACKUP_DIR..."
    $SUDO cp -a "$DEPLOY_DIR" "$BACKUP_DIR"
    info "Backup done: $BACKUP_DIR"
fi

# ---------- 3. Stop old service ----------
info "Stopping old service..."
$SUDO systemctl stop $SERVICE_NAME 2>/dev/null || true
$SUDO systemctl disable $SERVICE_NAME 2>/dev/null || true

# Kill any process on the new port (in case)
EXISTING_PID=$($SUDO lsof -ti :$SERVICE_PORT 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    warn "Killing process on port $SERVICE_PORT: PID $EXISTING_PID"
    $SUDO kill -9 $EXISTING_PID 2>/dev/null || true
fi

# ---------- 4. Install dependencies ----------
info "Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive

# Check if tools already exist
HAS_PYTHON=$(command -v python3 >/dev/null 2>&1 && echo yes || echo no)
HAS_NODE=$(command -v node >/dev/null 2>&1 && echo yes || echo no)
HAS_GIT=$(command -v git >/dev/null 2>&1 && echo yes || echo no)
HAS_SQLITE=$(command -v sqlite3 >/dev/null 2>&1 && echo yes || echo no)

info "Tools status: python=$HAS_PYTHON node=$HAS_NODE git=$HAS_GIT sqlite=$HAS_SQLITE"

# Only install if missing
NEED_INSTALL=0
[ "$HAS_PYTHON" = "no" ] && NEED_INSTALL=1
[ "$HAS_NODE" = "no" ] && NEED_INSTALL=1
[ "$HAS_GIT" = "no" ] && NEED_INSTALL=1
[ "$HAS_SQLITE" = "no" ] && NEED_INSTALL=1

if [ "$NEED_INSTALL" = "0" ]; then
    info "All required tools already installed, skipping apt install"
else
    case "$DISTRO" in
        ubuntu|debian)
            info "Using apt (some packages missing)..."
            # Check if apt is locked
            if $SUDO fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
                warn "apt lock held by another process. Waiting 10s and retrying..."
                sleep 10
                if $SUDO fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
                    warn "apt still locked, skipping installation. Tools may be missing."
                fi
            fi
            $SUDO apt-get install -y git python3 python3-venv python3-pip nodejs npm curl sqlite3 2>&1 | tail -5 || warn "apt-get had issues, continuing..."
            ;;
        centos|rhel|rocky|almalinux|fedora)
            info "Using yum/dnf..."
            PKG_MGR="yum"
            command -v dnf >/dev/null && PKG_MGR="dnf"
            $SUDO $PKG_MGR install -y git python3 python3-pip nodejs npm curl sqlite3 2>&1 | tail -5 || warn "$PKG_MGR had issues"
            $SUDO $PKG_MGR install -y python3-venv 2>&1 | tail -2 || true
            ;;
        *)
            warn "Unknown distro '$DISTRO'. Will rely on existing tools."
            if ! command -v python3 >/dev/null 2>&1; then
                error "python3 not found. Please install manually."
            fi
            if ! command -v node >/dev/null 2>&1; then
                error "node not found. Please install manually."
            fi
            if ! command -v git >/dev/null 2>&1; then
                error "git not found. Please install manually."
            fi
            ;;
    esac
fi

# Check tools
PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "NOT FOUND")
info "Python version: $PY_VERSION"
NODE_VERSION=$(node --version 2>/dev/null || echo "not installed")
info "Node version: $NODE_VERSION"

# ---------- 5. Wipe and prepare deploy dir ----------
info "Preparing deploy directory..."
$SUDO rm -rf "$DEPLOY_DIR"
$SUDO mkdir -p "$DEPLOY_DIR"
$SUDO chown -R $(whoami) "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# Try git clone first, fallback to local archive
if [ -f /tmp/channel-project.tar.gz ]; then
    info "Found local archive /tmp/channel-project.tar.gz, extracting..."
    tar -xzf /tmp/channel-project.tar.gz --strip-components=1
    info "Extracted from local archive"
elif command -v git >/dev/null 2>&1; then
    info "Trying git clone from GitHub..."
    if GIT_TERMINAL_PROMPT=0 git clone https://github.com/armyking001/channel-project.git . 2>&1 | tail -5; then
        info "Git clone successful"
    else
        error "Git clone failed. Please upload project as /tmp/channel-project.tar.gz"
    fi
else
    error "Neither git nor local archive available. Upload project as /tmp/channel-project.tar.gz"
fi

# ---------- 6. Configuration ----------
info "Generating backend config..."
cp backend/config.example.yaml backend/config.yaml

JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
info "JWT secret generated"

python3 << EOF
import yaml

with open('backend/config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

cfg['jwt']['secret_key'] = '$JWT_SECRET'
cfg['app']['cors_origins'] = [
    'http://localhost:$SERVICE_PORT',
    'http://127.0.0.1:$SERVICE_PORT',
    'http://0.0.0.0:$SERVICE_PORT',
    'http://172.16.10.92:$SERVICE_PORT',
    'http://172.16.10.92:$NGINX_PORT',
]

with open('backend/config.yaml', 'w', encoding='utf-8') as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
EOF

# ---------- 7. Python virtualenv ----------
info "Setting up Python virtualenv..."
DEPLOY_PY="$DEPLOY_DIR/backend/.venv"

# Try virtualenv, fallback to user-site packages
if python3 -m venv "$DEPLOY_PY" --system-site-packages 2>/dev/null; then
    info "venv created successfully"
    source "$DEPLOY_PY/bin/activate"
    pip install --upgrade pip -q 2>&1 | tail -3 || true
    pip install -r backend/requirements.txt -q 2>&1 | tail -5
elif python3 -m virtualenv "$DEPLOY_PY" --system-site-packages 2>/dev/null; then
    info "virtualenv created successfully"
    source "$DEPLOY_PY/bin/activate"
    pip install --upgrade pip -q 2>&1 | tail -3 || true
    pip install -r backend/requirements.txt -q 2>&1 | tail -5
else
    warn "Cannot create venv, installing to user-site..."
    pip3 install --user --break-system-packages -r backend/requirements.txt 2>&1 | tail -5 || {
        warn "Failed with --user, trying without..."
        pip3 install --break-system-packages -r backend/requirements.txt 2>&1 | tail -5
    }
    # Create a dummy venv dir to satisfy systemd
    mkdir -p "$DEPLOY_PY/bin"
    ln -sf /usr/bin/python3 "$DEPLOY_PY/bin/python"
fi

# ---------- 8. Build frontend ----------
info "Building frontend..."
cd "$DEPLOY_DIR/frontend"
npm install --silent
npm run build
cd "$DEPLOY_DIR"

if [ ! -f "backend/static/index.html" ]; then
    error "Frontend build failed: backend/static/index.html not found"
fi
info "Frontend built: backend/static/"

# ---------- 9. Create service user ----------
info "Ensuring service user: $SERVICE_USER"
$SUDO id $SERVICE_USER >/dev/null 2>&1 || $SUDO useradd -r -s /bin/false $SERVICE_USER

# ---------- 10. Database ----------
info "Setting database permissions..."
touch "$DB_FILE"
$SUDO chown -R $SERVICE_USER:$SERVICE_USER "$DEPLOY_DIR"
$SUDO chmod 750 "$DEPLOY_DIR"

# ---------- 11. systemd service ----------
info "Creating systemd service..."
$SUDO tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Channel Project Management System
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$DEPLOY_DIR/backend
Environment="PATH=$DEPLOY_DIR/backend/.venv/bin"
Environment="DEFAULT_ADMIN_PASSWORD=$ADMIN_PASSWORD"
ExecStart=$DEPLOY_DIR/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/var/log/$SERVICE_NAME.log
StandardError=append:/var/log/$SERVICE_NAME.err.log

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload
$SUDO systemctl enable $SERVICE_NAME

# ---------- 12. Start service ----------
info "Starting service..."
$SUDO systemctl start $SERVICE_NAME

info "Waiting for service ready..."
for i in {1..30}; do
    sleep 1
    if curl -s -f http://127.0.0.1:$SERVICE_PORT/api/auth/login -X POST -d "username=admin&password=$ADMIN_PASSWORD" >/dev/null 2>&1; then
        info "Service is up"
        break
    fi
    if [ "$i" -eq 30 ]; then
        error "Service start timeout. Check log: journalctl -u $SERVICE_NAME -n 50"
    fi
done

# ---------- 13. nginx config ----------
info "Verifying nginx config..."
NGINX_CONF=""
for conf in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf; do
    if [ -f "$conf" ] && grep -q "listen.*$NGINX_PORT\|listen.*26731" "$conf" 2>/dev/null; then
        NGINX_CONF="$conf"
        break
    fi
done

if [ -z "$NGINX_CONF" ]; then
    NGINX_CONF=$(grep -rl "26731" /etc/nginx/ 2>/dev/null | head -1)
fi

if [ -n "$NGINX_CONF" ] && [ -f "$NGINX_CONF" ]; then
    info "Found nginx config: $NGINX_CONF"
    $SUDO sed -i "s|proxy_pass http://127.0.0.1:[0-9]*;|proxy_pass http://127.0.0.1:$SERVICE_PORT;|g" "$NGINX_CONF"
    $SUDO sed -i "s|proxy_pass http://localhost:[0-9]*;|proxy_pass http://127.0.0.1:$SERVICE_PORT;|g" "$NGINX_CONF"
    $SUDO nginx -t && $SUDO systemctl reload nginx
    info "Nginx reloaded"
else
    warn "No nginx config found for port $NGINX_PORT"
fi

# ---------- 14. Firewall ----------
info "Opening ports in firewall..."
$SUDO ufw allow $SERVICE_PORT/tcp >/dev/null 2>&1 || true
$SUDO ufw allow $NGINX_PORT/tcp >/dev/null 2>&1 || true
$SUDO firewall-cmd --permanent --add-port=$SERVICE_PORT/tcp >/dev/null 2>&1 || true
$SUDO firewall-cmd --permanent --add-port=$NGINX_PORT/tcp >/dev/null 2>&1 || true
$SUDO firewall-cmd --reload >/dev/null 2>&1 || true

# ---------- 15. Clean database ----------
info "Cleaning database: keep only system admin..."
$SUDO systemctl stop $SERVICE_NAME
$SUDO sqlite3 "$DB_FILE" <<EOF
DELETE FROM approval_logs;
DELETE FROM projects;
DELETE FROM file_storage_records;
DELETE FROM file_storage_configs;
DELETE FROM audit_logs;
DELETE FROM users WHERE id != 1 OR role != 'admin';
EOF
info "Database cleaned"

$SUDO systemctl start $SERVICE_NAME
sleep 3

# ---------- 16. Verify ----------
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}UPGRADE COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP="172.16.10.92"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$NGINX_PORT/" 2>&1)
echo "Verification: nginx->app returns HTTP $HTTP_CODE"
echo ""
echo "Access URL:    http://${SERVER_IP}:${NGINX_PORT}/admin/"
echo "Default user:  admin"
echo "Default pass:  $ADMIN_PASSWORD"
echo ""
echo "Service:       $SERVICE_NAME (port $SERVICE_PORT, internal)"
echo "Nginx proxy:   $NGINX_PORT -> 127.0.0.1:$SERVICE_PORT"
echo "Deploy dir:    $DEPLOY_DIR"
echo "Backup of old: $BACKUP_DIR"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "1. Visit http://${SERVER_IP}:${NGINX_PORT}/admin/"
echo "2. Login with admin / admin123"
echo "3. Change password immediately!"
echo ""