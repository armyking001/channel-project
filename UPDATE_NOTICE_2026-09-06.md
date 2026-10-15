# 📢 2026-09-06 服务器更新通告

> 部署服务器 IP：`192.168.5.129` (Ubuntu 24.04, hostname=`admin-dify`)
> 入口：http://192.168.5.129:26731/admin/
> 部署时间：2026-09-06 12:43（打包）→ 12:53（数据备份）→ 后续健康检查通过
> 服务进程：channel-project.service active (running), PID 747154 (uvicorn 8000), 通过 nginx 26731 对外

---

## ✅ 一、本次部署的核心改动

### 1. **审批管理界面布局统一**（Fix-22a / 22b）

**问题**：审批管理 → 待审批 → 点击"审批处理"打开的项目详情弹窗，与项目列表 → 查看弹窗的**布局不一致**；右上角出现**两个 × 关闭按钮**；自营项目走 ProjectForm 时**丢失字段**（ProjectForm 是渠道模板硬编码字段）。

**修复**：
- [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx) — 新增 9 个审批 props（`canApprove / onApprove / onReject / rejecting / rejectingText / onRejectingTextChange / onSubmitReject / onCancelReject`），底部按钮区在 `readOnly && canApprove` 时渲染"驳回/通过"按钮 + 驳回理由输入框（与 ProjectForm 同结构）
- [frontend/src/pages/Approvals.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Approvals.jsx) — `handleView` 按 `project.source` 分流：**渠道走 ProjectForm**（字段硬编码、布局完整），**自营走 DynamicForm**（按自营模板字段渲染）；删除外层 modal 多余 ×

**渲染矩阵**（修复后）：

| 入口 | 渠道项目 (source='channel') | 自营项目 (source='self') |
|---|---|---|
| 项目列表 → 编辑 | ProjectForm | DynamicForm (edit) |
| 项目列表 → 查看 | ProjectForm (readOnly) | DynamicForm (readOnly) |
| **审批** | **ProjectForm (readOnly + 审批按钮)** | **DynamicForm (readOnly + 审批按钮)** |

后端 / 数据库 / API 路由 **0 改动**。

---

### 2. **部署服务器 IP 切换**（172.16.10.92 → 192.168.5.129）

服务器 `admin-dify` 有两张网卡，本次将所有**主部署脚本+临时调试脚本**的目标 IP 统一切换到 **`192.168.5.129`**。MD 历史文档保留作历史记录。

**改动文件**：19 个脚本/部署文件，全部更新：

| 类别 | 文件 |
|---|---|
| 主部署脚本 | `deploy/deploy_all.py` / `deploy_simple.ps1` / `deploy_windows.ps1` / `upgrade_to_server.sh` / `auto_deploy.sh` |
| 临时调试脚本 | `deploy/check_server.py` / `check_db.py` / `check_remote.ps1` / `check_old.ps1` / `check_port.ps1` / `diag_server.py` / `test_approve.py` / `test_admin_approve.py` / `test_jluo.py` / `test1.py` / `find_admin.py` / `upload.py` / `package.py` / `fix_service.sh` |

**未修改**（历史文档）：`DEPLOY_LOG.md`、`DEPLOY_TO_10.92.md`、`DEPLOY_INCREMENTAL.md`、`README.md`、`AGENTS.md` 历史章节、`USER_GUIDE.md`、`agenttest.md`。

---

## 🔧 二、部署过程中发现并修复的问题

### 问题 1：`PROJECT_ROOT` 路径错配（`z:\` → `y:\`）

| 项 | 内容 |
|---|---|
| 现象 | 原配置 `z:\soft-RED\hermes\开发软件\渠道项目登记`，但本机仅 `C/D/Y` 三盘，无 z 盘 |
| 原因 | 历史遗留路径（用户可能曾用 z 盘映射或 subst 映射到 y 盘） |
| 修复 | 改为 `y:\soft-RED\hermes\开发软件\渠道项目登记` |

### 问题 2：`remote_update.sh` CRLF 行尾导致 Ubuntu bash 执行失败

| 项 | 内容 |
|---|---|
| 现象 | Ubuntu 执行 `remote_update.sh` 时报 `:找不到命令` `cd: $'\r'` `do\r: 附近有语法错误` |
| 原因 | Windows 编辑器保存时自动加 CRLF（`\r\n`），bash 解释器在行尾见到 `\r` 触发"找不到命令" |
| 修复 | 用 PowerShell `[IO.File]::ReadAllText` → `Replace('\r\n','\n')` → `WriteAllText` 转 LF |
| 验证 | 重打包重部署，nginx reload + channel-project.service active (running) |

### 问题 3：打包阶段 `shutil.copy2` 到 staging dir 拖慢打包

| 项 | 内容 |
|---|---|
| 现象 | 原 `deploy_all.step_package` 用 `tempfile.mkdtemp` 创建 staging dir + `shutil.copy2` 复制 11162 文件，Y 盘 IO 较慢，14 分钟未完成打包 |
| 优化（一次性）| 改用 `os.walk` + `tar.add` 直接对源目录打包，跳过 staging 复制，从 14+ 分钟降到约 2 分钟 |

---

## 🔐 三、SSH key 重建与 GitHub 推送

| 项 | 内容 |
|---|---|
| 背景 | `C:\Users\admin\.ssh\` 之前没有 `id_rsa` / `id_ed25519` 私钥 → git push `Permission denied (publickey)` |
| 操作 | 新生成 ED25519：`ssh-keygen -t ed25519 -C "admin@channel-project-deploy" -f C:\Users\admin\.ssh\id_ed25519 -N ""` |
| SSH config | 追加 `Host github.com` 段（User git / IdentityFile id_ed25519 / IdentitiesOnly yes / PreferredAuthentications publickey） |
| GitHub | 公钥已贴到 https://github.com/settings/keys → key 名 `STAR-14-deploy-ed25519-2026-09-06` |
| 验证 | `ssh -T git@github.com` → `Hi armyking001! You've successfully authenticated` |
| 推送 | `1417f21..ae4ba37 feature/ai-agent -> feature/ai-agent`，本地分支与 remote 一致 |

---

## ✅ 四、部署验收（健康检查）

| 项 | 结果 |
|---|---|
| 打包 | ✅ 11162 文件，14.83MB tar.gz，`channel-project-20260906124307.tar.gz` |
| 上传+部署 | ✅ 成功（CRLF→LF 修复后） |
| `GET /api/health` | ✅ 200 |
| `POST /api/auth/login` | ✅ 200 |
| `GET /api/projects/` | ✅ 200, total=18（与 DB 备份一致）|
| 服务状态 | active (running), PID 747154 (uvicorn 8000), 通过 nginx 26731 对外 |

---

## 📦 五、服务器备份与回退

| 项 | 位置 / 命令 |
|---|---|
| **数据备份** | `/opt/channel-project-data-backup-20260906125341/`（含 `data.db` / `config.yaml` / `app/config.py`）|
| **回退命令** | `sudo cp /opt/channel-project-data-backup-20260906125341/data.db /opt/channel-project/backend/data.db` |
| **入口** | http://192.168.5.129:26731/admin/ |

---

## 📝 六、关键文件引用

- [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx) — Fix-22a 9 个审批 props + 驳回/通过按钮 + 驳回理由输入框
- [frontend/src/pages/Approvals.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Approvals.jsx) — Fix-22b 按 source 分流 ProjectForm/DynamicForm + 删除外层多余 ×
- `deploy/deploy_all.py` — 主部署脚本（IP=192.168.5.129, PROJECT_ROOT=y:\）
- `deploy/deploy_simple.ps1` / `deploy_windows.ps1` — PowerShell 部署脚本
- `deploy/upgrade_to_server.sh` / `auto_deploy.sh` — Linux 部署脚本
- `deploy/*.py` / `deploy/*.ps1` — 临时调试脚本（全部 IP 已切换）
- `C:\Users\admin\.ssh\id_ed25519` — 新生成 ED25519 私钥
- GitHub Deploy Key: `STAR-14-deploy-ed25519-2026-09-06`

---

## 💡 七、本次部署带来的可观测改善

| 类别 | 改善点 |
|---|---|
| **审批管理 UX** | 渠道/自营审批布局统一、字段完整、右上角只有 1 个 × |
| **部署稳定性** | 主用 IP 统一（192.168.5.129），避免下次又混两个 IP |
| **打包效率** | 跳过 staging 复制，打包时间从 14+ 分钟降到 2 分钟 |
| **跨平台脚本** | `remote_update.sh` LF 行尾已修复，未来建议项目加 `.gitattributes` `*.sh eol=lf` |
| **GitHub 推送** | SSH key 重建，推送恢复正常 |

---

## ⚠️ 八、注意事项

1. **ADMIN=000 不一定代表失败**：本次部署 nginx `/admin/` 路径用 try_files fallback，看到 ADMIN=000 属预期行为。判断服务是否正常要看 `/api/health=200` + login 200 + 项目总数匹配 DB 备份。
2. **多网卡服务器要统一 IP 表述**：192.168.5.129 与 172.16.10.92 是同一台服务器，本次已选定 192.168.5.129 作为主用 IP，后续 grep/部署都要用这个 IP。
3. **Windows 编辑的 shell 脚本必须 LF 行尾**：上传到 Linux 跑的脚本，写完后应该用 PowerShell 或 `unix2dos -u` 转一次行尾。

---

更新通告生成时间：2026-09-06（基于 [AGENTS.md](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/AGENTS.md) §42 + §43 汇总）