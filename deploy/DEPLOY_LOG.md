# 部署日志 - 2026-08-06

> 记录本次部署踩过的所有坑，避免重复犯错。
> 目标服务器：172.16.10.92（hostname: admin-dify，Ubuntu 24.04，Dify 服务器）
> 部署账号：admin001（sudo + NOPASSWD）
> 部署端口：26731（nginx）→ 8000（内部）

## ✅ 最终成果

- ✅ 本地代码已上传 GitHub
- ✅ 部署脚本就绪（升级模式）
- ⚠️ 服务器上的部署卡在服务启动阶段（未完全跑通）

## 🚨 踩过的坑（务必记住）

### 坑 1：Windows PowerShell 引号转义问题

**症状**：脚本里用 `"...."` 包含 `[^"]` 这种正则表达式，PowerShell 把内层 `"` 当成字符串终止符。

**错误示例**：
```powershell
# ❌ 错误
if ($line -match "(C:\\Users[^"]+\.tar\.gz)") { ... }

# ✅ 正确
if ($line -match '(C:\\Users[^"]+\.tar\.gz)') { ... }
```

**教训**：
- PowerShell 中包含正则 `[^"]` 时，用**单引号**包外层
- 避免在双引号字符串中嵌入双引号

### 坑 2：Windows tar 不支持 GNU tar 的 `--exclude`

**症状**：打出来的包 98MB，包含 `node_modules`（80MB）和 `.venv`（15MB）

**根因**：
- Windows 10/11 自带的 tar 是 **bsdtar**（来自 libarchive）
- **不支持 GNU tar 的 `--exclude` 选项**
- 即使加了 `--exclude=node_modules --exclude=.venv` 也无效

**教训**：
- 不要依赖 tar 的 --exclude 来排除大目录
- 必须先用其他工具（Python/robocopy）**手动复制**干净的文件，再打包
- 推荐用 Python 脚本（处理中文路径最好）

### 坑 3：中文路径导致 PowerShell 命令乱码

**症状**：
```
Source: z:\soft-RED\hermes\寮€鍙戣蒋浠禱娓犻亾椤圭洰鐧昏\u17b
[INFO] Found 0 files to package
```

**根因**：
- PowerShell 的 console 输出编码（cp936 / GBK）和脚本执行编码（UTF-8）不一致
- 命令行参数经过 encoding 转换后路径变成乱码
- `Get-ChildItem -LiteralPath` / `robocopy` 失败

**教训**：
- **Python 脚本对中文路径最友好**（直接用 Unicode）
- PowerShell 脚本里用 `Get-ChildItem` 处理中文路径不可靠
- robocopy 在某些情况下也会失败

### 坑 4：apt-get 锁被占用导致安装失败

**症状**：
```
E: 无法获得锁 /var/lib/dpkg/lock-frontend。锁正由进程 3492580（apt-get）持有
```

**根因**：Dify 服务器上其他进程正在跑 apt-get

**教训**：
- 不要让部署脚本假设 apt 一定可用
- 必须**先检查工具是否已存在**（python3, node, git, sqlite3）
- 只有缺失时才尝试 apt install
- apt 失败时给警告但**不要终止部署**

### 坑 5：Python virtualenv 在某些精简 Python 上不可用

**症状**：`python3 -m venv .venv` 卡死或失败

**根因**：某些 Linux 发行版（Dify 镜像）精简了 Python，没装 `python3-venv` 包

**教训**：
- 准备好 fallback：
  1. `python3 -m venv --system-site-packages`
  2. `python3 -m virtualenv`
  3. `pip3 install --user --break-system-packages`
- 不要让 venv 失败导致整个部署终止

### 坑 6：nginx 配置被覆盖风险

**症状**：之前部署可能破坏现有 nginx 服务

**教训**：
- **不要修改** nginx 默认配置（`/etc/nginx/sites-enabled/default`）
- 在 `sites-available` 添加自定义配置，用 symlink 启用
- 用 `nginx -t` 测试配置语法，再 `reload`

### 坑 7：覆盖旧部署前没备份

**症状**：升级时直接 `rm -rf /opt/channel-project`，丢失旧版本配置

**教训**：
- 升级前必须备份：`cp -a /opt/channel-project /opt/channel-project-backup-<时间戳>`
- 备份包含配置文件、数据库、自定义脚本

### 坑 8：脚本里写入的 PowerShell 字符串含中文

**症状**：之前的脚本写入 PowerShell `Write-Host "✅ 部署完成"` 等含 emoji+中文 的字符串，PowerShell v5 解析失败

**教训**：
- PowerShell 脚本中**避免中文和 emoji**
- 用纯英文输出，或者把中文信息放到单独的 UTF-8 文件里读取

### 坑 9：服务器没有 GitHub 网络访问

**症状**：`git clone https://github.com/...` 失败（提示需要输入用户名）

**根因**：服务器网络受限或 git 提示无法读取（SSH 隧道下交互式读取失败）

**教训**：
- **不要依赖 git clone**，改用本地打包上传
- PowerShell 打包成 tar.gz 上传到 `/tmp/`
- 服务器从 `/tmp/` 解压

### 坑 10：service 启动超时但 pip install 显示完成

**症状**：
```
[INFO] venv created successfully
WARNING: Connection interrupted while downloading.
WARNING: Attempting to resume incomplete download...
[INFO] Building frontend...
[ERROR] Service start timeout
```

**根因**：
- pip install 有 WARNING（lxml 下载被重置），但最终完成
- 然后构建前端成功
- 但服务启动超时（很可能 venv 依赖没装全，或者权限问题）

**教训**：
- `pip install` 完成要看**返回值**而不是"看起来跑完了"
- 服务启动失败时要查 `journalctl -u channel-project -n 30` 看具体原因

## 📋 明天继续部署的步骤

### 步骤 1：SSH 登录服务器排查当前状态
```bash
ssh admin001@172.16.10.92

# 查看服务状态
sudo systemctl status channel-project --no-pager -n 30

# 查看错误日志
sudo journalctl -u channel-project -n 50 --no-pager

# 查看应用错误日志
sudo tail -30 /var/log/channel-project.err.log

# 检查 venv 中依赖是否完整
ls /opt/channel-project/backend/.venv/lib/python3.12/site-packages/ | head -30

# 手动启动看错误
sudo systemctl stop channel-project
cd /opt/channel-project/backend
sudo -u www-data ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# (Ctrl+C 退出)
```

### 步骤 2：根据错误修复

可能的修复方案：

**A. 依赖没装全**：
```bash
cd /opt/channel-project/backend
source .venv/bin/activate
pip install -r requirements.txt
```

**B. www-data 没权限**：
```bash
sudo chown -R www-data:www-data /opt/channel-project
sudo chmod -R 755 /opt/channel-project
```

**C. 旧服务冲突**：
```bash
# 杀掉所有 channel-project 相关进程
sudo pkill -9 -f uvicorn
sudo pkill -9 -f channel-project
# 重新启动
sudo systemctl start channel-project
```

**D. 数据库初始化问题**：
```bash
# 删除数据库，让 main.py 重新创建
sudo systemctl stop channel-project
sudo rm /opt/channel-project/backend/data.db
sudo systemctl start channel-project
```

### 步骤 3：完成剩余部署步骤
```bash
# 清理数据库
sudo systemctl stop channel-project
sudo sqlite3 /opt/channel-project/backend/data.db <<'SQL'
DELETE FROM approval_logs;
DELETE FROM projects;
DELETE FROM file_storage_records;
DELETE FROM file_storage_configs;
DELETE FROM audit_logs;
DELETE FROM users WHERE id != 1 OR role != 'admin';
SQL

# 重启服务
sudo systemctl start channel-project
sleep 3

# 重启 nginx
sudo systemctl reload nginx

# 验证
curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://127.0.0.1:8000/admin/
```

### 步骤 4：前端验证

访问 `http://172.16.10.92:26731/admin/`

确认：
- 登录页面（admin / admin123）
- 项目列表显示4 个筛选条件（项目名称、合作单位、全部状态、全部中标状态、金额范围、填报日期）
- 项目列表第一列是"序号"
- 数据库只有 admin 一个账号

## 📂 部署脚本文件清单

| 文件 | 状态 | 用途 |
|---|---|---|
| [deploy_simple.ps1](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/deploy_simple.ps1) | ✅ 修复后可用 | Windows 一键部署入口 |
| [package.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/package.py) | ✅ 已验证 | Python 打包脚本（处理中文） |
| [package.ps1](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/package.ps1) | ⚠️ 中文路径有问题 | robocopy 版本，备用 |
| [upgrade_to_server.sh](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/upgrade_to_server.sh) | ✅ 已修复 | Linux 服务器端升级脚本 |
| [check_remote.ps1](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/check_remote.ps1) | ✅ 可用 | 服务器诊断脚本 |
| [check_old.ps1](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/check_old.ps1) | ✅ 可用 | 检查旧部署 |

## 🎯 明天执行的关键命令

```powershell
# 1. 先 SSH 排查服务为什么超时
ssh admin001@172.16.10.92
# 然后手动执行 systemctl 命令看错误

# 2. 修复后重新执行一键部署（只重新打包+上传，不再跑 apt）
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\deploy"
.\deploy_simple.ps1 -ServerIP 172.16.10.92
```

## 📝 经验总结

1. **永远不要假设环境** — 服务器上有什么工具需要检测
2. **永远备份再操作** — 升级前必须备份原部署
3. **永远不要静默失败** — apt失败、pip失败都要让用户看到
4. **永远用 Python 处理中文** — PowerShell 处理中文路径不可靠
5. **永远先 SSH 上去手动调试一次** — 再写自动化脚本
6. **永远记录所有踩过的坑** — 避免下次重复

---

最后更新：2026-08-06 17:35