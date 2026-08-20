# 渠道项目登记系统 - 一键部署指南

## 🚀 快速部署

### 前置条件

- **服务器**：Linux（Ubuntu 20.04+ / Debian 11+）
- **权限**：root 账号
- **网络**：可访问 GitHub（拉取代码）

### 部署架构

```
Nginx (80)  →  FastAPI/Uvicorn (8000)  →  SQLite
                ↓
            React 前端 (静态文件)
```

部署完成后：
- **访问地址**：`http://<服务器IP>/admin/`
- **服务端口**：8000（FastAPI）+ 80（Nginx 反向代理）
- **数据库**：SQLite `/opt/channel-project/backend/data.db`

---

## 📋 一键部署（推荐）

#### 方法一：本地 Windows 一键部署（推荐）

适合在本地 Windows 机器上直接部署到 Linux 服务器。

**步骤**：

1. **安装 sshpass**（如果未安装）：
   - 下载：https://sourceforge.net/projects/sshpass/
   - 解压后将 `sshpass.exe` 加入 PATH

2. **运行部署脚本**：
   ```powershell
   cd 渠道项目登记\deploy
   .\deploy_windows.ps1
   ```
   按提示输入：
   - 服务器 IP（默认 `172.16.10.92`）
   - root 密码

3. **等待 5-10 分钟**，脚本会自动完成：
   - 安装系统依赖（Python 3, Node.js, Nginx, SQLite）
   - 从 GitHub 拉取最新代码
   - 创建 Python 虚拟环境并安装依赖
   - 构建前端
   - 生成 JWT 密钥
   - 创建 systemd 服务
   - 配置 Nginx 反向代理
   - 初始化数据库（仅保留 admin 账号）
   - 启动服务

4. **访问系统**：
   ```
   http://172.16.10.92/admin/
   ```
   默认账号：`admin` / `admin123`（**登录后立即修改！**）

#### 方法二：手动部署

如果自动部署失败，可手动执行：

```bash
# 1. SSH 登录服务器
ssh root@172.16.10.92

# 2. 上传 deploy_to_server.sh
# (从本地 Windows 上传或复制内容)

# 3. 执行部署
chmod +x deploy_to_server.sh
bash deploy_to_server.sh
```

---

## 🔧 部署后管理

### 服务管理

```bash
# 查看服务状态
systemctl status channel-project

# 查看实时日志
journalctl -u channel-project -f

# 重启服务
systemctl restart channel-project

# 停止服务
systemctl stop channel-project

# 启动服务
systemctl start channel-project
```

### 部署目录

```
/opt/channel-project/         # 项目根目录
├── backend/                  # FastAPI 代码
│   ├── .venv/                # Python 虚拟环境
│   ├── config.yaml           # 配置文件（含 JWT 密钥、WebDAV 配置）
│   ├── data.db               # SQLite 数据库
│   └── static/               # 前端构建产物
├── frontend/                 # 前端源码
│   ├── node_modules/
│   └── package.json
└── .git/                     # Git 仓库
```

### 日志位置

```
/var/log/channel-project.log     # 应用日志
/var/log/channel-project.err.log # 错误日志
journalctl -u channel-project    # systemd 日志
```

### 更新部署

```bash
cd /opt/channel-project
git pull origin main
cd backend && source .venv/bin/activate
cd ../frontend && npm run build
systemctl restart channel-project
```

---

## 🔐 安全配置（生产环境必须）

部署完成后，**强烈建议**完成以下安全配置：

### 1. 修改默认管理员密码

- 登录后 → 右上角用户菜单 → 修改密码
- 密码要求：至少 8 位，包含大小写字母和数字

### 2. 修改 JWT 密钥

编辑 `/opt/channel-project/backend/config.yaml`：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# 复制输出替换 jwt.secret_key 的值

systemctl restart channel-project
```

### 3. 启用 HTTPS（推荐）

```bash
# 安装 certbot
apt-get install -y certbot python3-certbot-nginx

# 申请证书（替换为你的域名）
certbot --nginx -d your-domain.com

# 自动续期
certbot renew --dry-run
```

### 4. 配置防火墙

```bash
# 查看当前规则
ufw status

# 仅开放必要端口
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw reload
```

### 5. 数据库备份

```bash
# 手动备份
cp /opt/channel-project/backend/data.db /backup/data-$(date +%Y%m%d).db

# 设置每日自动备份（添加到 crontab）
echo "0 2 * * * cp /opt/channel-project/backend/data.db /backup/data-\$(date +\%Y\%m\%d).db" | crontab -
```

---

## 🐛 常见问题

### Q1：部署后无法访问？

```bash
# 检查服务状态
systemctl status channel-project

# 检查端口监听
ss -tlnp | grep 8000

# 检查 Nginx
nginx -t
systemctl status nginx

# 检查防火墙
ufw status
```

### Q2：登录失败，提示密码错误？

确认默认管理员账号已创建：
```bash
sqlite3 /opt/channel-project/backend/data.db "SELECT id, username, role FROM users"
```

如果只有空结果，重启服务：
```bash
systemctl restart channel-project
```

### Q3：前端显示空白页？

```bash
# 检查前端产物
ls -la /opt/channel-project/backend/static/

# 重新构建
cd /opt/channel-project/frontend
npm run build
systemctl restart channel-project
```

### Q4：如何修改默认管理员密码（部署后）？

修改部署脚本中的 `ADMIN_PASSWORD` 变量，然后重新运行部署。或者登录后在系统中修改。

---

## 📦 部署包内容

| 文件 | 说明 |
|---|---|
| `deploy_to_server.sh` | 服务器端主部署脚本（Linux 执行） |
| `deploy_windows.ps1` | Windows 一键部署脚本（本地执行） |
| `README.md` | 本文件 |

---

## 📞 技术支持

部署过程中遇到问题：
1. 查看日志：`journalctl -u channel-project -n 100`
2. 联系系统管理员或开发团队

---

> 📅 最后更新：2026-08-06
> 🌟 适用版本：v1.0.0+