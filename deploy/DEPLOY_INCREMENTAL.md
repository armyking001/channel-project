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

## 🚨 数据回滚

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
最后更新：2026-08-14（一键部署脚本 deploy_all.py 上线）
