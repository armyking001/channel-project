#!/bin/bash
# 增量更新脚本 — 只更新代码，保留数据库和已配置的服务
set +e  # 不让单步失败中断

echo "================================================"
echo "Channel Project INCREMENTAL UPDATE"
echo "保留: 数据库 data.db, 服务配置, 系统级依赖"
echo "================================================"

# 1. 停止服务
echo "[1/7] 停止服务..."
sudo systemctl stop channel-project 2>/dev/null
sudo fuser -k 8000/tcp 2>/dev/null
sleep 3
echo "  DONE"

# 2. 备份当前部署的 data.db 和 config
echo "[2/7] 备份数据文件..."
BACKUP_DIR=/opt/channel-project-data-backup-$(date +%Y%m%d%H%M%S)
sudo mkdir -p "$BACKUP_DIR"
sudo cp /opt/channel-project/backend/data.db "$BACKUP_DIR/" 2>/dev/null
sudo cp /opt/channel-project/backend/config.yaml "$BACKUP_DIR/" 2>/dev/null
sudo cp /opt/channel-project/backend/app/config.py "$BACKUP_DIR/" 2>/dev/null
ls "$BACKUP_DIR"
echo "  DONE (备份到 $BACKUP_DIR)"

# 3. 删除旧代码（保留 data.db 所在目录）
echo "[3/7] 删除旧代码（保留数据）..."
sudo rm -rf /opt/channel-project/backend/app
sudo rm -rf /opt/channel-project/backend/services
sudo rm -rf /opt/channel-project/backend/routers
sudo rm -rf /opt/channel-project/frontend
sudo rm -rf /opt/channel-project/deploy
sudo rm -rf /opt/channel-project/backend/static
echo "  DONE"

# 4. 解压新代码（会覆盖，但不会动 backend/data.db）
echo "[4/7] 解压新代码..."
cd /opt/channel-project
sudo tar -xzf /tmp/channel-project.tar.gz
ls | head -10
echo "  DONE"

# 5. 恢复数据文件
echo "[5/7] 恢复数据文件..."
sudo cp "$BACKUP_DIR/data.db" /opt/channel-project/backend/data.db
sudo cp "$BACKUP_DIR/config.yaml" /opt/channel-project/backend/config.yaml 2>/dev/null
ls /opt/channel-project/backend/data.db
ls /opt/channel-project/backend/config.yaml 2>/dev/null
echo "  DONE"

# 6. 重新构建前端
echo "[6/7] 重新构建前端..."
cd /opt/channel-project/frontend
sudo npm install 2>&1 | tail -3
sudo npm run build 2>&1 | tail -5
ls /opt/channel-project/backend/static/
echo "  DONE"

# 6.5 检查并修复 Nginx client_max_body_size（大文件上传必需）
echo "[6.5/7] 调整 Nginx body 限制..."
NGINX_CONF=$(sudo find /etc/nginx -name "*.conf" 2>/dev/null | xargs grep -l "channel-project\|proxy_pass.*8000" 2>/dev/null | head -3)
if [ -z "$NGINX_CONF" ]; then
    NGINX_CONF=$(sudo find /etc/nginx -name "channel*" -o -name "*channel*" 2>/dev/null | head -3)
fi
if [ -n "$NGINX_CONF" ]; then
    for f in $NGINX_CONF; do
        if ! sudo grep -q "client_max_body_size" "$f" 2>/dev/null; then
            sudo sed -i 's|^\(\s*\)server {|&\n\1client_max_body_size 500m;|' "$f" || true
            echo "  + client_max_body_size 500m 已添加到 $f"
        else
            # 已是更大的值则保留,否则替换为 500m
            CURRENT=$(sudo grep "client_max_body_size" "$f" | head -1 | grep -oE '[0-9]+[kmg]?')
            case "$CURRENT" in
                *[0-9][kmg]) echo "  = $f 已有 client_max_body_size $CURRENT, 保留";;
                *) sudo sed -i 's|client_max_body_size [^[:space:]]*;|client_max_body_size 500m;|' "$f" && echo "  * $f 改为 500m";;
            esac
        fi
    done
    sudo nginx -t 2>&1 | tail -2 && sudo systemctl reload nginx 2>&1 && echo "  nginx reloaded"
else
    echo "  ⚠️ 未找到 Nginx 反向代理配置(跳过,可能部署是直连8000端口)"
fi

# 7. 启动服务
echo "[7/7] 启动服务..."
sudo systemctl start channel-project
sleep 5
sudo systemctl status channel-project --no-pager -n 5

# 测试
echo ""
echo "=== TEST ==="
curl -s -o /dev/null -w "ADMIN=%{http_code}\n" http://127.0.0.1:8000/admin/
echo "=== DONE ==="
echo ""
echo "数据保留: $BACKUP_DIR"
echo "如有问题可恢复: sudo cp $BACKUP_DIR/data.db /opt/channel-project/backend/data.db"