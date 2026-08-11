# 渠道项目管理系统 - 增量更新流程（保留数据）

> **标准增量更新流程** — 每次代码修改后只需要执行这3个命令，保留所有数据
> 目标服务器：172.16.10.92（admin001 / akwj210627）

## 🎯 三步更新

### Step 1: 打包本地代码

**Windows PowerShell**：
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

### Step 2: 一键增量更新（打包+上传+部署一条龙）

**Windows PowerShell**（用 Step 1 输出的实际 tarball 路径）：

```powershell
python -c "
import subprocess
SSHPASS = r'C:\Users\jwang\AppData\Local\Microsoft\WindowsApps\sshpass.exe'
PWD_FILE = r'C:\Users\jwang\AppData\Local\Temp\spwd.tmp'
TAR_FILE = r'<替换为Step1的tarball完整路径>'
SCRIPT = r'z:\soft-RED\hermes\开发软件\渠道项目登记\deploy\remote_update.sh'
with open(PWD_FILE, 'w') as f: f.write('akwj210627')
r1 = subprocess.run([SSHPASS, '-f', PWD_FILE, 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', TAR_FILE, 'admin001@172.16.10.92:/tmp/channel-project.tar.gz'], capture_output=True, text=True, timeout=60)
print('TAR UPLOAD:', r1.returncode)
r2 = subprocess.run([SSHPASS, '-f', PWD_FILE, 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', SCRIPT, 'admin001@172.16.10.92:/tmp/remote_update.sh'], capture_output=True, text=True, timeout=30)
print('SCRIPT UPLOAD:', r2.returncode)
r3 = subprocess.run([SSHPASS, '-f', PWD_FILE, 'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', 'admin001@172.16.10.92', 'chmod +x /tmp/remote_update.sh && sudo bash /tmp/remote_update.sh'], capture_output=True, text=True, timeout=900)
print('RUN EXIT:', r3.returncode)
print(r3.stdout)
import os
os.remove(PWD_FILE)
"
```

**预期最后输出**：
```
[7/7] 启动服务...
Active: active (running)
=== TEST ===
ADMIN=200
=== DONE ===
```

### Step 3: 浏览器验证

1. 打开 `http://172.16.10.92:26731/admin/`
2. **Ctrl+Shift+R** 强制刷新
3. 登录测试新功能

## 📦 保留内容

| 项目 | 保留？ | 位置 |
|---|---|---|
| 数据库（用户/项目/审批） | ✅ 保留 | `/opt/channel-project/backend/data.db` |
| WebDAV 配置 | ✅ 保留 | `/opt/channel-project/backend/config.yaml` |
| systemd 服务配置 | ✅ 保留 | `/etc/systemd/system/channel-project.service` |
| nginx 配置 | ✅ 保留 | `/etc/nginx/sites-enabled/channel*` |
| 系统级 Python 依赖 | ✅ 保留 | `/usr/local/lib/python3.12/dist-packages/` |
| 数据备份（每次更新自动） | ✅ 创建 | `/opt/channel-project-data-backup-YYYYMMDDHHMMSS/` |

## 🔄 替换内容

| 项目 | 替换？ |
|---|---|
| backend/app/*.py | ✅ 替换 |
| backend/requirements.txt | ✅ 替换 |
| frontend/src/* | ✅ 替换 |
| backend/static/*（前端构建产物） | ✅ 替换 |
| deploy/ | ✅ 替换 |

## ⚠️ 关键避坑点

1. **永远用增量更新**（`remote_update.sh`），**不要用完整部署**（`auto_deploy.sh`）
2. **永远 Ctrl+Shift+R** 强制刷新浏览器
3. **永远不调 apt**（Dify 锁会冲突）
4. **永远用清华镜像** 装 Python 依赖（避免超时）
5. **永远用 `--ignore-installed`** 标志
6. **永远先 `fuser -k 8000/tcp` 再启动服务**（避免端口冲突）
7. **永远先 `mkdir -p backend/static` 再 npm run build**（避免目录不存在）
8. **永远用 `import webdav3` 不是 `import webdavclient3`**

## 🚨 数据回滚（如有问题）

如果新版本有问题，回滚数据：

```bash
# SSH 到服务器
ssh admin001@172.16.10.92

# 停服务
sudo systemctl stop channel-project

# 看有哪些备份
ls -la /opt/channel-project-data-backup-*/

# 恢复指定备份（替换 YYYYMMDDHHMMSS）
sudo cp /opt/channel-project-data-backup-YYYYMMDDHHMMSS/data.db /opt/channel-project/backend/data.db
sudo cp /opt/channel-project-data-backup-YYYYMMDDHHMMSS/config.yaml /opt/channel-project/backend/config.yaml

# 重启服务
sudo systemctl start channel-project
```

## 📁 关键文件

| 文件 | 用途 |
|---|---|
| [package.py](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/deploy/package.py) | 本地打包脚本 |
| [remote_update.sh](file:///z:/soft-RED/hermes/%E5%BC%80%E5%8F%91%E8%BD%AF%E4%BB%B6/%E6%B8%A0%E9%81%93%E9%A1%B9%E7%9B%AE%E7%99%BB%E8%AE%B0/deploy/remote_update.sh) | 服务器端增量更新脚本 |

## 🎯 下次更新的标准操作

1. 修改本地代码
2. **执行本文件 Step 1 的命令**打包
3. **执行本文件 Step 2 的命令**部署（替换 tarball 路径）
4. **执行本文件 Step 3** 浏览器验证

完成！

最后更新：2026-08-07 11:50（增量更新流程验证成功）