# 渠道项目管理系统 - 增量部署流程（保留数据）

> **一键增量部署** — 打包 + 上传 + 部署 + 测试 + GitHub 同步，一条命令搞定
> 目标服务器：172.16.10.92（admin001 / akwj210627）

## 🚀 一键部署

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\deploy"
python deploy_all.py
```

**可选参数**：
- `--no-deploy` — 只打包 + Git 同步，不部署到服务器
- `--no-git` — 只部署，不同步到 GitHub

## 🚨 升级失败快速恢复

> **触发条件**：升级/部署后服务 502、启动失败、health 接口不通、配置损坏等
> **设计目标**：**一条命令恢复最近的健康系统状态，不动用户数据**

### 用户指令

> "按 DEPLOY_INCREMENTAL.md 恢复最近一次系统"

### 一键恢复命令

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\deploy"
python deploy_all.py --restore
```

### 自动完成的 6 个步骤

| 步骤 | 说明 |
|------|------|
| 1. 探测环境 | 检查 SSH 通道 + 服务器状态 + 服务类型（systemd / 旧 systemd） |
| 2. 识别冲突 | 检测端口 8000 占用、多个 systemd service（如 channel.service vs channel-project.service） |
| 3. 禁用旧服务 | `systemctl disable channel` 等旧 service + `kill -9` 旧进程 |
| 4. 还原备份 | 从 `/opt/channel-project-data-backup-YYYYMMDDHHMMSS/` 还原 **最新的备份** |
| 5. 启动服务 | `systemctl restart channel-project` + 等启动完成 |
| 6. 健康检查 | `/api/health` + 项目列表 API + nginx 转发链路 |

### 数据保留策略

**严格不动用户数据**：
- ✅ `data.db`（项目/用户/审批/通知所有数据）只从最近一次备份还原
- ✅ 不重置用户密码
- ✅ 不删除任何项目
- ✅ 不动 WebDAV 上传的文件
- ⚠️ 升级后**新增**的数据（备份后产生的）会丢失

### 恢复前诊断（必须）

`--restore` 模式会**先打印诊断报告**，需用户确认后才能执行：

```
============================================================
🚨 升级失败恢复模式
============================================================
当前状态:
  - 端口 8000 占用: PID 3111303 (channel.service /opt/channel/backend/)
  - systemd 失败: channel-project.service status=1/FAILURE
  - 备份目录: /opt/channel-project-data-backup-20260906125341/

将执行的操作:
  1. systemctl stop channel-project channel
  2. systemctl disable channel
  3. kill -9 3111303 3111310 3111311 (旧 uvicorn)
  4. cp /opt/channel-project-data-backup-20260906125341/data.db -> 当前 data.db
  5. cp /opt/channel-project-data-backup-20260906125341/config.yaml -> 当前 config.yaml
  6. systemctl start channel-project
  7. 健康检查 (curl /api/health 200 + nginx 转发 200)

是否继续? [y/N]
```

### 适用场景与对应动作

| 场景 | 自动动作 |
|------|---------|
| 端口 8000 被占（多个 uvicorn） | kill 旧 PID + disable 旧 service |
| config.yaml 缺字段（如 jwt.secret_key） | 从备份还原 config.yaml |
| models.py 引入新表失败 | 还原 models.py + 保留新数据迁移 |
| static/index.html 缺失 | 从备份还原 |
| systemd service status=1/FAILURE | 还原全部代码 + 重启 |
| 用户报告"按之前的样子回滚" | 全量还原到最近一次成功部署 |
| 数据被误删 | 仅还原 data.db（其他代码不动） |

### 与正常升级的区别

| 维度 | 正常部署 `deploy_all.py` | 恢复模式 `--restore` |
|------|------------------------|---------------------|
| 代码来源 | 本地源码 | **服务器备份目录** |
| 数据来源 | 保留当前 data.db | **从备份还原** |
| GitHub 同步 | ✅ 自动 commit + push | ❌ 不提交代码变更 |
| 前端构建 | ✅ 服务器端 npm run build | ❌ 还原备份的 static/ |
| 耗时 | 2-3 分钟 | 30 秒 |
| 风险 | 中（覆盖旧代码） | 低（恢复已知好的状态） |

### 关键避坑点（恢复场景）

1. **禁用旧 service 时机**：必须先 `stop` 再 `disable`，否则重启循环会一直拉起旧进程
2. **kill -9 必须包含 master + worker**：uvicorn --workers N 时 master PID + N 个 worker PID 都要杀
3. **data.db 备份不能丢**：每次成功部署后**自动**在 `/opt/channel-project-data-backup-YYYYMMDDHHMMSS/` 创建完整快照（含 data.db + config.yaml + 所有代码）
4. **手动跑 uvicorn 拿 traceback**：`sudo systemctl status X` 看不到 Python 错误，必须 `cd /opt/X && sudo /usr/bin/python3 -m uvicorn app.main:app 2>&1 | head -60`
5. **不要修改服务器 config.yaml 的 database.url**：服务器是 Linux，DB url 必须是 `/opt/...` 路径，不能改成本地 Windows 路径

### 自动完成的 9 个步骤

| 步骤 | 说明 | 自动？ |
|------|------|--------|
| 1. 打包代码 | `python package.py` 逻辑内置，排除 data.db/log/node_modules | ✅ |
| 2. 上传 tar | scp 到 `/tmp/channel-project.tar.gz` | ✅ |
| 3. 上传脚本 | scp `remote_update.sh` 到 `/tmp/` | ✅ |
| 4. 远程部署 | SSH 执行：停服→备份→更新代码→恢复数据→构建前端→启动 | ✅ |
| 5. 保留数据 | data.db、config.yaml 自动备份并恢复 | ✅ |
| 6. 构建前端 | 服务器端 `npm run build` 输出到 `backend/static/` | ✅ |
| 7. 启动+测试 | systemd 启动 + 健康检查 + 登录测试 + 项目列表测试 | ✅ |
| 8. GitHub 同步 | `git add -A && git commit && git push` | ✅ |
| 9. 结果报告 | 汇总各步骤状态和耗时 | ✅ |

### 预期输出

```
[HH:MM:SS] [START] ╔══════════════════════════════════════════════════╗
[HH:MM:SS] [START] ║  渠道项目管理系统 - 一键增量部署               ║
[HH:MM:SS] [START] ╚══════════════════════════════════════════════════╝
[HH:MM:SS] [INFO] Step 1/6: 打包本地代码
[HH:MM:SS] [INFO] Step 2/6: 上传 tar 包到服务器
[HH:MM:SS] [INFO] Step 3/6: 上传部署脚本
[HH:MM:SS] [INFO] Step 4/6: 执行远程部署（停服→备份→更新代码→恢复数据→构建前端→启动）
[HH:MM:SS] [INFO] Step 5/6: 服务器 API 测试
[HH:MM:SS] [INFO] Step 6/6: 同步到 GitHub
[HH:MM:SS] [DONE] ╔══════════════════════════════════════════════════╗
[HH:MM:SS] [DONE] ║              部署结果汇总报告                   ║
[HH:MM:SS] [DONE] ╠══════════════════════════════════════════════════╣
[HH:MM:SS] [DONE] ║  打包         ✅ 通过                            ║
[HH:MM:SS] [DONE] ║  部署         ✅ 通过                            ║
[HH:MM:SS] [DONE] ║  测试         ✅ 通过                            ║
[HH:MM:SS] [DONE] ║  GitHub      ✅ 通过                            ║
[HH:MM:SS] [DONE] ║  耗时: 120.5s                                   ║
[HH:MM:SS] [DONE] ╚══════════════════════════════════════════════════╝
```

## 📦 保留内容

| 项目 | 保留？ | 位置 |
|------|--------|------|
| 数据库（用户/项目/审批） | ✅ | `/opt/channel-project/backend/data.db` |
| WebDAV 配置 | ✅ | `/opt/channel-project/backend/config.yaml` |
| systemd 服务配置 | ✅ | `/etc/systemd/system/channel-project.service` |
| nginx 配置 | ✅ | `/etc/nginx/sites-enabled/channel*` |
| 系统级 Python 依赖 | ✅ | `/usr/local/lib/python3.12/dist-packages/` |
| 数据备份（每次更新自动） | ✅ | `/opt/channel-project-data-backup-YYYYMMDDHHMMSS/` |

## 🔄 替换内容

| 项目 | 替换？ |
|------|--------|
| backend/app/*.py | ✅ |
| backend/requirements.txt | ✅ |
| frontend/src/* | ✅ |
| backend/static/*（前端构建产物） | ✅ |
| deploy/ | ✅ |

## ⚠️ 关键避坑点

1. **永远用增量更新**（`remote_update.sh`），不要用完整部署（`auto_deploy.sh`）
2. **浏览器 Ctrl+Shift+R** 强制刷新
3. **不调 apt**（Dify 锁会冲突）
4. **用清华镜像**装 Python 依赖（避免超时）
5. **用 `--ignore-installed`** 标志
6. **先 `fuser -k 8000/tcp`** 再启动服务（避免端口冲突）
7. **先 `mkdir -p backend/static`** 再 npm run build
8. **用 `import webdav3`** 不是 `import webdavclient3`
9. **`parent_id` 清空**：后端 `update_user` 必须用 `model_fields_set` 判断，不能用 `is not None`（否则无法清空为 NULL）
10. **winpty 部署**：`sshpass.exe` 可能损坏，`deploy_all.py` 已内置 winpty 方案

## 🚨 数据回滚（手动版）

> ⚠️ **推荐使用上面的 `--restore` 模式**，本节为应急手动步骤

```bash
ssh admin001@172.16.10.92
sudo systemctl stop channel-project
ls -la /opt/channel-project-data-backup-*/
sudo cp /opt/channel-project-data-backup-YYYYMMDDHHMMSS/data.db /opt/channel-project/backend/data.db
sudo cp /opt/channel-project-data-backup-YYYYMMDDHHMMSS/config.yaml /opt/channel-project/backend/config.yaml
sudo systemctl start channel-project
```

## 📁 关键文件

| 文件 | 用途 |
|------|------|
| [deploy_all.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/deploy_all.py) | **一键部署脚本**（打包+上传+部署+测试+Git） |
| [package.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/package.py) | 本地打包脚本（独立使用） |
| [remote_update.sh](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/remote_update.sh) | 服务器端增量更新脚本 |
| [deploy_via_winpty.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/deploy_via_winpty.py) | winpty 部署脚本（旧版，已被 deploy_all.py 替代） |

## 📝 AGENTS.md 自动记录

每次部署后，AI 助手应自动在 `AGENTS.md` 的变更日志中添加记录，格式：

```markdown
### 🗓 YYYY-MM-DD（功能简述）

#### ① 功能名称 ✅
- **需求**：用户提的需求
- **实现**：
  - 修改的文件和逻辑
- **关联文件**：
  - `path/to/file.py`
- **测试**：本地/服务器测试结果
```

---
最后更新：2026-09-08（新增 `🚨 升级失败快速恢复` 章节与 `--restore` 模式；基于本次 hotfix 教训：端口冲突 / 旧 service / config.yaml 不应改动 Linux 路径）
