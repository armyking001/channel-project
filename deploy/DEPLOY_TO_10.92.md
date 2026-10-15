# 渠道项目管理系统 - 服务器部署完整说明

> 目标服务器：172.16.10.92（hostname: admin-dify，Ubuntu 24.04，Dify 服务器）
> 部署账号：admin001（sudo + NOPASSWD）
> 部署端口：26731（nginx）→ 8000（内部 uvicorn）
> 部署目录：/opt/channel-project
> 访问地址：http://172.16.10.92:26731/admin/
> 默认账号：admin / Admin@2026（首次登录后必须修改）

## ✅ 已完成的一次性配置

以下已经在服务器上完成，后续部署不需要再操作：

1. **sudo NOPASSWD 已配置**（`/etc/sudoers.d/admin001-nopasswd`）
2. **Python 依赖已装**（`/usr/local/lib/python3.12/dist-packages/`）
   - fastapi==0.115.0
   - uvicorn==0.30.6
   - sqlalchemy==2.0.35
   - pydantic==2.9.2
   - pydantic-settings==2.5.2
   - python-jose==3.3.0
   - passlib==1.7.4
   - python-multipart==0.0.12
   - pyyaml==6.0.2
   - openpyxl==3.1.5
   - xlrd==2.0.1
   - webdavclient3==3.14.7
   - python-docx==1.2.0
   - requests==2.32.3
3. **nginx 已配置**：`/etc/nginx/sites-enabled/` 下有 channel 配置，监听 26731 代理到 127.0.0.1:8000
4. **systemd 服务已创建**：`/etc/systemd/system/channel-project.service`，已 enable
5. **pip 清华镜像已可用**：`https://pypi.tuna.tsinghua.edu.cn/simple`

## 🔥 之前踩过的坑（务必避开）

### 坑 1：apt 锁被 Dify 占用
- 症状：`E: Unable to acquire the dpkg frontend lock`
- 解决：**不调 apt**，依赖已装齐

### 坑 2：8000 端口被残留进程占用
- 症状：`[Errno 98] address already in use`
- 解决：先 `sudo fuser -k 8000/tcp` 再启动

### 坑 3：pip 装 fastapi 失败（typing-extensions 是 Debian 包）
- 解决：用清华镜像 + `--ignore-installed` 标志
- 实际已用：`sudo pip3 install --break-system-packages --ignore-installed -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`

### 坑 4：webdavclient3 模块名是 webdav3
- 解决：应用代码用 `import webdav3`（不要用 `webdavclient3`）

### 坑 5：vite.config.js 输出到 ../backend/static/ 而不是 dist/
- 解决：构建时**不要 cp dist/ 到 static/**，npm run build 直接写 static/

### 坑 6：vite: not found
- 原因：tar 包不包含 node_modules
- 解决：**服务器上必须先 `npm install`** 再 `npm run build`

### 坑 7：服务启不来因为 main.py 加载 static/index.html 时目录不存在
- 解决：先 `sudo mkdir -p /opt/channel-project/backend/static`

### 坑 8：pip 卡住（连接超时）
- 解决：用清华镜像 + `--default-timeout=300`

### 坑 9：kill 旧 uvicorn 不彻底
- 解决：用 `sudo fuser -k 8000/tcp` 强杀

### 坑 10：后端代码 import 失败（依赖没装）
- 解决：先 `sudo python3 -c "import fastapi, uvicorn, sqlalchemy; print('OK')"` 验证

### 坑 11：vite 构建输出到错误目录
- vite.config.js 配置：`outDir: '../backend/static'`
- 构建后：`/opt/channel-project/backend/static/index.html` 和 `assets/`

## 🚀 标准部署流程（每次更新执行）

### Step 0: 本地打包（在 Windows PowerShell）

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\deploy"
python package.py
```

**预期输出**：
```
[INFO] Found 1258 files to package
[INFO] Tarball size: 4.35 MB
[INFO] Ready to upload: C:\Users\jwang\AppData\Local\Temp\channel-project-YYYYMMDDHHMMSS.tar.gz
```

记录 tarball 完整路径。

### Step 1: 上传到服务器（在 Windows PowerShell）

```powershell
sshpass -p "akwj210627" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL "C:\Users\jwang\AppData\Local\Temp\channel-project-YYYYMMDDHHMMSS.tar.gz" admin001@172.16.10.92:/tmp/channel-project.tar.gz
```

**预期**：100% 完成，无报错。

### Step 2: SSH 到服务器（PowerShell）

```powershell
ssh admin001@172.16.10.92
```

输入密码 `akwj210627`。

### Step 3: 停止旧服务、清理、解压（在服务器）

```bash
# 1. 停服务并清干净端口
sudo systemctl stop channel-project
sudo fuser -k 8000/tcp 2>/dev/null
sleep 3

# 2. 备份并删除旧部署
if [ -d /opt/channel-project ]; then
    sudo mv /opt/channel-project /opt/channel-project-backup-$(date +%Y%m%d%H%M%S)
fi
sudo rm -rf /opt/channel-project
sudo mkdir -p /opt/channel-project
sudo mkdir -p /opt/channel-project/backend/static

# 3. 解压新代码
cd /opt/channel-project
sudo tar -xzf /tmp/channel-project.tar.gz

# 4. 验证解压
ls | head -10
```

**预期输出**：
```
backend
frontend
deploy
README.md
...
```

### Step 4: 安装/构建前端（在服务器）

```bash
# 1. 装前端依赖（如果 package.json 没变，跳过）
cd /opt/channel-project/frontend
sudo npm install 2>&1 | tail -3

# 2. 构建（直接输出到 ../backend/static/）
sudo npm run build 2>&1 | tail -10

# 3. 验证 static 目录
ls /opt/channel-project/backend/static/
ls /opt/channel-project/backend/static/assets/
```

**预期输出**：
```
assets  index.html  logo_login.png  logo.png
index-XXX.js  index-XXX.css
```

### Step 5: 验证后端依赖（在服务器）

```bash
# 验证 Python 依赖完整
sudo python3 -c "import fastapi, uvicorn, sqlalchemy, pydantic, pydantic_settings, jose, passlib, multipart, openpyxl, docx, requests; import webdav3; print('OK ALL DEPS')"
```

**预期**：`OK ALL DEPS`

如果报 `ModuleNotFoundError`：
```bash
# 用清华镜像安装缺失的包
sudo pip3 install --break-system-packages --ignore-installed --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>
```

### Step 6: 启动服务（在服务器）

```bash
sudo systemctl start channel-project
sleep 5
sudo systemctl status channel-project --no-pager -n 10
```

**预期**：`Active: active (running)`

### Step 7: 测试访问（在服务器）

```bash
curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://127.0.0.1:8000/admin/
curl -s http://127.0.0.1:8000/admin/ | head -3
```

**预期**：
- HTTP=200
- HTML 内容包含 `<title>渠道项目管理系统</title>`

### Step 8: 浏览器验证

1. 打开 `http://172.16.10.92:26731/admin/`
2. 按 **Ctrl+Shift+R** 强制刷新
3. 登录：`admin` / `Admin@2026`
4. 验证新功能（取决于本次更新内容）

## 🛑 故障排查速查

### 服务启动失败：address already in use
```bash
sudo systemctl stop channel-project
sudo fuser -k 8000/tcp 2>/dev/null
sleep 3
sudo systemctl start channel-project
```

### 服务启动失败：ModuleNotFoundError
```bash
# 看是哪个模块
sudo journalctl -u channel-project -n 30 --no-pager
# 装缺失的
sudo pip3 install --break-system-packages --ignore-installed --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>
```

### 前端看不到更新
```bash
cd /opt/channel-project/frontend
sudo rm -rf node_modules
sudo npm install
sudo npm run build
sudo systemctl restart channel-project
```
然后浏览器 **Ctrl+Shift+R**。

### 数据库乱了想重置
```bash
sudo systemctl stop channel-project
sudo rm -f /opt/channel-project/backend/data.db
sudo systemctl start channel-project
# 重新创建默认管理员 admin / Admin@2026
```

### 端口被占看是谁
```bash
sudo ss -tlnp | grep :8000
# 看 PID
ps aux | grep <PID> | grep -v grep
```

## 📁 服务器目录结构

```
/opt/channel-project/                  # 部署根
├── backend/                           # 后端代码
│   ├── app/                          # FastAPI 应用
│   │   ├── main.py                   # 入口
│   │   ├── models.py                 # ORM 模型
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── routers/                  # 路由
│   │   └── services/                 # 服务层
│   ├── static/                       # 前端构建产物（npm run build 输出）
│   │   ├── index.html
│   │   ├── assets/
│   │   ├── logo.png
│   │   └── logo_login.png
│   ├── data.db                       # SQLite 数据库
│   ├── config.yaml                   # 应用配置
│   └── requirements.txt              # Python 依赖
├── frontend/                         # 前端源码
│   ├── src/                          # React 组件
│   ├── package.json
│   ├── vite.config.js                # 配置输出到 ../backend/static/
│   └── node_modules/                 # npm install 生成
└── deploy/                           # 部署脚本（参考用）

/etc/systemd/system/channel-project.service   # systemd 服务
/etc/nginx/sites-enabled/                     # nginx 站点配置
/var/log/channel-project.log                  # 应用 stdout
/var/log/channel-project.err.log              # 应用 stderr
```

## 🔑 关键密码和账号

| 资源 | 值 |
|---|---|
| 服务器 SSH 账号 | admin001 |
| 服务器 SSH 密码 | akwj210627 |
| Web 默认账号 | admin |
| Web 默认密码 | Admin@2026 |
| 数据库 | SQLite (本地文件) |
| GitHub | armyking001/channel-project (公开仓库) |

## 📝 部署命令速查（完整版）

每次更新时，按顺序执行：

```bash
# === 步骤 1: 本地打包 (Windows PowerShell) ===
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\deploy"
python package.py
# 记录 tarball 路径

# === 步骤 2: 上传 (Windows PowerShell) ===
sshpass -p "akwj210627" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL "<TARBALL_PATH>" admin001@172.16.10.92:/tmp/channel-project.tar.gz

# === 步骤 3-7: 服务器操作 (SSH) ===
ssh admin001@172.16.10.92
# 密码: akwj210627

# 服务器上依次执行:
sudo systemctl stop channel-project
sudo fuser -k 8000/tcp 2>/dev/null
sleep 3
[ -d /opt/channel-project ] && sudo mv /opt/channel-project /opt/channel-project-backup-$(date +%Y%m%d%H%M%S)
sudo rm -rf /opt/channel-project
sudo mkdir -p /opt/channel-project/backend/static
cd /opt/channel-project && sudo tar -xzf /tmp/channel-project.tar.gz
ls | head -10

cd /opt/channel-project/frontend
sudo npm install 2>&1 | tail -3
sudo npm run build 2>&1 | tail -10
ls /opt/channel-project/backend/static/

sudo python3 -c "import fastapi, uvicorn, sqlalchemy, pydantic, pydantic_settings, jose, passlib, multipart, openpyxl, docx, requests; import webdav3; print('OK')"

sudo systemctl start channel-project
sleep 5
sudo systemctl status channel-project --no-pager -n 5
curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://127.0.0.1:8000/admin/

# === 步骤 8: 浏览器访问 ===
# http://172.16.10.92:26731/admin/
# Ctrl+Shift+R 强制刷新
# 登录: admin / Admin@2026
```

## ⚠️ 重要注意事项

1. **永远不要 `apt install`**（Dify 锁会冲突）
2. **永远用清华镜像**（避免超时）
3. **永远用 `--ignore-installed`**（避免 typing-extensions 错误）
4. **永远先 `fuser -k 8000/tcp` 再启动服务**（避免端口冲突）
5. **永远先 `mkdir -p backend/static` 再 npm run build**（避免目录不存在）
6. **永远用 `import webdav3` 不是 `import webdavclient3`**
7. **永远在浏览器按 Ctrl+Shift+R 强制刷新**（避免缓存）
8. **永远备份当前部署再更新**（脚本已自动）

## 🔧 重要脚本清单

| 文件 | 用途 |
|---|---|
| [package.py](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/deploy/package.py) | 本地打包脚本（处理中文路径） |
| [auto_deploy.sh](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/deploy/auto_deploy.sh) | 服务器端自动部署脚本（备用） |
| [fix_service.sh](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/deploy/fix_service.sh) | 修复 systemd 服务脚本（备用） |
| [DEPLOY_LOG.md](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/DEPLOY_LOG.md) | 历史部署踩坑记录 |

最后更新：2026-08-07