# AI 协作指南（AGENTS.md）

> 本文件供任何 AI 助手（Trae / Cursor / Copilot / Claude / GPT 等）快速理解本项目架构、历史决策、当前痛点。
> **修改代码前必读**。

## 🏗️ 项目一句话总结

**渠道项目登记与审批管理系统** —— 政企/事业单位内部用的项目管理 SaaS。技术栈：FastAPI + SQLAlchemy + React + Vite。功能：项目登记、文件管理（支持 WebDAV 远程 NAS）、审批、报表、用户管理。

## 📁 关键文件速查

| 任务 | 看这个文件 |
|---|---|
| 前端文件管理弹窗 | `frontend/src/components/ProjectForm.jsx`（line 92-150 是 fetchFiles，最常被改）|
| 后端 list-files / upload | `backend/app/routers/file_storage.py` |
| WebDAV 客户端 | `backend/app/services/webdav_client.py`（注意 `_space_variants_for_project` 函数：处理"采购项目"↔"采 购项目"路径兼容）|
| 用户登录 / 申请账号 | `backend/app/routers/auth.py` |
| 用户管理前端 | `frontend/src/pages/UserManagement.jsx` |
| 拼音→账号生成 | `backend/app/services/pinyin_util.py`（字典可能不全，遇到生僻字需补）|
| 数据库模型 | `backend/app/models.py` |
| API schemas | `backend/app/schemas.py` |
| 配置加载 | `backend/app/main.py:21 load_config()` |

## 🚨 已踩过的坑（AI 不要重复犯错）

### 坑 1：ProjectForm 文件列表不显示
- **症状**：编辑项目时"文件管理"区一直显示"暂无文件"
- **真因**：两个 useEffect 并发请求 → race condition → tenderFiles 被刷成 []
- **教训**：
  - 文件系统类功能，**后端是路径的唯一事实来源**
  - 前端不要用 `target_dir` 字符串拼接猜测路径
  - API 调用必须用 `project_id` 让后端查表
  - 已修复：合并 useEffect + `isSubscribed` 标志位 + 串行 await

### 坑 2：路径空格 "采购项目" vs "采 购项目"
- **背景**：WebDAV 目录里历史数据有空格变体
- **真因**：前端 slice 字符串插空格的逻辑太脆弱（错位）
- **教训**：用 `str.replace('采购项目', '采 购项目')` 精准替换，不要启发式

### 坑 3：硬编码敏感信息
- 已检查：无 `Synology2020` / `admin123` / 真实 IP 残留
- 配置（JWT secret / WebDAV 密码）在 `backend/config.yaml`，**`.gitignore` 已排除**
- 默认管理员密码从 `DEFAULT_ADMIN_PASSWORD` 环境变量读

### 坑 4：时间显示为 UTC，差 8 小时
- **症状**：项目创建时间是 `06:31`，但系统时间是 `14:31`
- **真因**：后端 SQLAlchemy 用 `datetime.utcnow()` 写入的是 UTC 时间；前端 `dayjs(s)` 直接 format 会把 UTC 当本地时间显示。
- **教训**：
  - **不要**用 `dayjs(s).format('YYYY-MM-DD HH:mm')` 直接显示 UTC 时间字符串
  - **必须**用 `dayjs.utc(s).tz('Asia/Shanghai').format('YYYY-MM-DD HH:mm')`
  - 或者用原生 API：`new Date(s+'Z').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })`
  - 需要导入 `dayjs/plugin/utc` 和 `dayjs/plugin/timezone` 并 `dayjs.extend(...)`
- **涉及文件**：`Projects.jsx` / `Approvals.jsx` / `UserManagement.jsx` / `AuditLogs.jsx` 全部已加时区转换

### 坑 5：WebDAV 上 PROPFIND / MKCOL 报 405（Method Not Allowed）
- **症状**：创建项目时，WebDAV 返回 405，前端报错"父目录未就绪"
- **真因**：NAS WebDAV 服务不支持 PROPFIND（资源浏览）和 MKCOL（创建目录），但目录其实**已经存在**（管理员在 NAS 上手动建过）。
- **教训**：
  - 405 **不等于**目录不存在，是 NAS 不支持该方法
  - `ensure_webdav_folders` 已改造：PROPFIND/MKCOL 报 405 时视为"目录已存在"，继续后续流程
- **涉及文件**：`backend/app/services/file_storage.py:ensure_webdav_folders`

### 坑 6：onDelete 回调没传 id 导致 404
- **症状**：撤回模式下点"删除项目"，确认后项目还在
- **真因**：`onDelete={handleDelete}` 直接传函数引用，调用时 `handleDelete()` 没传 id → `DELETE /api/projects/undefined` → 404
- **教训**：父组件传回调给子组件时，**必须**用 `() => handler(args)` 绑定参数，不要直接传函数引用

### 坑 7：DB template 字段不会自动跟随代码默认值更新
- **症状**：前端传 `responsible_sales='测试人A'` → 预览路径仍是 `刘建辉+...`（创建者姓名）
- **真因**：`FileStorageConfig.template` 是数据库**配置项**，不是代码常量。即使代码 `default='{responsible_sales}+...'` 已改，**已存在的数据库行不会自动更新**。模板里**没有 `{responsible_sales}` 占位符** → 永远只渲染 `{real_name}`。
- **教训**：
  - 涉及模板字符串拼接的"业务配置项"都要**双重保障**：① 代码默认值更新；② 启动时**显式迁移 UPDATE** 数据库。
  - **不要相信"render 函数接受了 responsible_sales 参数就以为会用上"**——模板字符串才是真相。
  - 部署完必须 `SELECT template FROM file_storage_config;` 验证。
- **涉及文件**：`backend/app/main.py`（UPDATE脚本）+ `backend/app/models.py`（默认值）

## 🎯 当前功能模块状态

| 模块 | 状态 | 备注 |
|---|---|---|
| 项目登记 | ✅ 稳定 | 字段级权限 + 创建人列 + 北京时区 |
| 项目撤回 | ✅ 稳定 | 仅普通账号可撤回自己的项目；含"撤回修改"模式 |
| 文件管理 | ✅ 稳定 | 已修 race condition + 405 兼容 |
| WebDAV | ✅ 稳定 | 兼容空格变体 + 405 当已存在 |
| 申请账号 | ✅ 稳定 | 公开接口 + 返回初始密码 + 支持同名复用 |
| 用户审批 | ✅ 稳定 | 5 个 Tab + 批量操作 + 自动填初始密码 |
| 修改密码 | ✅ 稳定 | 所有角色可改自己的密码 |
| 报表 | ✅ 稳定 | Excel 导出 |
| 审计日志 | ✅ 稳定 | 全操作留痕 + 北京时区 |

## 🔧 常用调试模式

### 后端日志
```bash
tail -f backend/app_debug.log
# 或
Get-Content backend/uvicorn.err.log -Wait
```

### 重启后端
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2
cd backend
Start-Process -FilePath python -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -RedirectStandardOutput 'uvicorn.out.log' -RedirectStandardError 'uvicorn.err.log' -WindowStyle Hidden
```

### 重新构建前端
```powershell
cd frontend
npm run build   # 输出到 ../backend/static/
```

### 端到端诊断：调 list-files
```python
import requests
r = requests.post('http://127.0.0.1:8000/api/file-storage/list-files', 
                  json={'project_id': 47, 'folder_type': 'tender'},
                  headers={'Authorization': f'Bearer {TOKEN}'})
print(r.json())
```

## 🛠️ 部署架构

- **生产部署**：`backend/main.py` 把 `static/` 挂到 `/admin/`
- **前端构建产物**：`backend/static/index.html` + `assets/index-*.js`
- **开发模式**：前端 `npm run dev`（端口 5173）→ Vite 代理到后端 8000

## 📝 修改代码的检查清单

1. **是否需要更新 schema？** → `backend/app/schemas.py`
2. **是否需要更新数据库模型？** → `backend/app/models.py`（旧表用 `ALTER TABLE` 兼容）
3. **前端是否需要新 API 调用？** → `frontend/src/api/index.jsx`
4. **是否影响其他角色？** → 检查 `require_admin` / `require_important_or_admin`
5. **是否需要写审计？** → `audit.log(...)` 留痕
6. **时间显示一定要用北京时区**：`dayjs.utc(s).tz('Asia/Shanghai').format(...)` 或 `toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })`
7. **WebDAV 操作不要因为 405 就报错**：可能是 NAS 不支持该方法，目录其实存在
8. **commit message 写清楚动机**，不只写"what"

## 🆘 遇到问题先查

1. `backend/uvicorn.err.log` - 后端启动错误
2. `backend/app_debug.log` - 业务日志（含 list-files 的 target_dir）
3. 浏览器 DevTools → Network → 看实际请求和响应
4. `DEBUG_NOTE.md` - 历史 bug 分析（很可能有答案）
5. `git log --oneline -20` - 最近改了什么

---

## 📜 变更日志（Chronological Changelog）

按时间倒序记录「用户提的需求」与「已实施的改动」，方便后续 AI 助手快速理解近期上下文。

---

### 🗓 2026-08-12（责任销售字段 + 文件夹命名模板升级）

#### ① Project 增加「责任销售」字段（必填）✅
- **需求**：项目基本信息加"责任销售"字段（必填），用于命名项目目录。
- **实现**：
  - `backend/app/models.py:Project`：新增 `responsible_sales: Optional[str] = NULL`，迁移脚本 `ALTER TABLE projects ADD COLUMN responsible_sales VARCHAR(100)`。
  - `backend/app/schemas.py`：
    - `ProjectBase` 加 `responsible_sales` 字段。
    - `ProjectCreate.responsible_sales: str = Field(..., min_length=1)` 强制必填。
    - `ProjectUpdate` 和 `ProjectResponse` 加 `responsible_sales`。
  - `frontend/src/components/ProjectForm.jsx`：
    - 表单 state 加 `responsible_sales`。
    - 输入框标签加红星 `<Star />`（必填）。
    - `validate()` 加 `errs.responsible_sales = '责任销售必填'`。
    - 提交时 `responsible_sales: form.responsible_sales?.trim() || ''`。
- **关联文件**：
  - `backend/app/models.py:Project.responsible_sales`
  - `backend/app/main.py`（ALTER TABLE 迁移）
  - `backend/app/schemas.py:ProjectCreate.responsible_sales`
  - `frontend/src/components/ProjectForm.jsx`

#### ② 文件夹命名模板升级：`{real_name}` → `{responsible_sales}` ✅
- **需求**：生成的目录名从"姓名+项目名称+建立时间"改为"责任销售+项目名称+建立时间"。
- **实现**：
  - `backend/app/models.py:FileStorageConfig.template`：默认值从 `'{real_name}+{project_name}+{date}'` 改为 `'{responsible_sales}+{project_name}+{date}'`。
  - `backend/app/services/file_storage.py:render_base_folder`：模板默认 `'{responsible_sales}+...'`；`responsible_sales` 为空时**兜底**用 `real_name`（兼容老数据）。
  - `backend/app/routers/file_storage.py:preview_path`：传入 `responsible_sales`；**移除 `existing_tender_folder/existing_bid_folder` 兜底逻辑**（保证预览实时跟随字段变化）。
  - `backend/app/main.py`：迁移脚本增加 `UPDATE file_storage_config SET template='...' WHERE template='{real_name}+...'`。
  - `backend/app/schemas.py:PathPreviewRequest`：新增 `responsible_sales: Optional[str] = None`。
  - `frontend/src/components/ProjectForm.jsx`：预览逻辑增加必填校验——只有 `project_name + responsible_sales` 都填了才调 API，否则显示"请先填写项目名称和责任销售"占位符。`useEffect` 依赖增加 `form.responsible_sales`。
- **关联文件**：
  - `backend/app/models.py:FileStorageConfig.template` 默认值
  - `backend/app/services/file_storage.py:render_base_folder`
  - `backend/app/routers/file_storage.py:preview_path`
  - `backend/app/main.py`（template 迁移）
  - `backend/app/schemas.py:PathPreviewRequest.responsible_sales`
  - `frontend/src/components/ProjectForm.jsx`（预览逻辑 + useEffect 依赖）

#### ③ 坑：DB template 字段不会自动更新（关键）⚠️
- **症状**：前端传 `responsible_sales='测试人A'` → 预览路径仍是 `刘建辉+项目名称+...`（创建者姓名）。
- **真因**：后端 `FileStorageConfig.template` 是数据库**配置项**，不是代码常量。即使代码默认改了，**已存在的数据库行不会自动更新**。模板里**没有 `{responsible_sales}` 占位符** → 永远只渲染 `{real_name}`。
- **教训**：
  - 凡是涉及模板字符串拼接的"业务配置项"都要**双重保障**：① 代码默认值更新；② 启动时**显式迁移 UPDATE** 数据库。
  - **不要相信 "render 函数接受了 responsible_sales 参数就以为会用上"**——模板才是真相。
- **排查方法**：直接查 DB `SELECT template FROM file_storage_config;`。
- **解决**：手动 UPDATE 服务器 DB 一次；后续重启自动 UPDATE。

---

### 🗓 2026-08-10（多角色权限 + 撤回机制 + 时区修复）

#### ① 修改密码功能（所有角色可用）✅
- **需求**：除系统管理员外，其他账号（普通/重要/档案）登录后也能改自己的密码。
- **实现**：
  - `backend/app/routers/auth.py`：新增 `POST /api/auth/change-password`，验证旧密码 + 新密码一致性 + 6 位以上 + 不可与旧密码相同 + 写审计日志。
  - `backend/app/models.py:AuditAction`：新增 `USER_PASSWORD_CHANGE`。
  - `frontend/src/components/Layout.jsx`：顶栏右上角用户名下拉菜单，新增「修改密码」「退出登录」两项。
  - `frontend/src/components/ChangePasswordModal.jsx`（新文件）：旧密码 / 新密码 / 确认密码 三字段，含可见性切换、客户端校验、修改成功后自动退出登录。
- **关联文件**：
  - `backend/app/routers/auth.py:change_password`
  - `backend/app/models.py:AuditAction`
  - `frontend/src/components/Layout.jsx`
  - `frontend/src/components/ChangePasswordModal.jsx`

#### ② 审批弹窗自动填入申请时生成的初始密码 ✅
- **需求**：管理员审批账号时，初始密码应自动填入申请时生成的那个密码（可改可不改），姓名仍只读。
- **实现**：
  - `backend/app/models.py:User` 新增 `pending_password` 字段（明文存储临时密码，待审批通过后清除）。
  - `backend/app/main.py` 加 `ALTER TABLE users ADD COLUMN pending_password VARCHAR(64)` 兼容旧库。
  - `backend/app/schemas.py:UserResponse` 新增 `pending_password` 字段；`UserUpdate` 支持 `password` 更新。
  - `backend/app/routers/auth.py:apply_account`：申请时把生成的 8 位密码同时写入 `pending_password`。
  - `backend/app/routers/auth.py:apply_account` 复用逻辑（同名 pending 申请）：**排除已驳回用户** (`is_rejected=True`)，返回之前的 `pending_password`，并把 `!PENDING_` 前缀和 `__rej_<ts>` 后缀清理掉返回给前端。
  - `backend/app/routers/users.py:update_user`：支持更新密码并清除 `pending_password`。
  - `frontend/src/pages/UserManagement.jsx:openApprove`：自动预填 `pending_password`；兼容老数据自动生成 8 位密码。
- **关联文件**：
  - `backend/app/models.py:User.pending_password`
  - `backend/app/main.py`（ALTER TABLE）
  - `backend/app/schemas.py:UserResponse / UserUpdate`
  - `backend/app/routers/auth.py:apply_account`
  - `backend/app/routers/users.py:update_user`
  - `frontend/src/pages/UserManagement.jsx:openApprove`

#### ③ 重要账号 + 系统管理员在项目列表的权限统一化 ✅
- **需求**：
  - 系统管理员：项目列表只有「编辑、查看、删除」，通过/驳回去审批管理。
  - 重要账号：项目列表只有「查看」（编辑/审批去审批管理）。
  - 普通账号：编辑（上传文件）+ 查看 +（自己的项目在待审批/已驳回时可撤回）。
  - 档案管理：只查看。
- **实现**：`frontend/src/pages/Projects.jsx` 重构操作矩阵。
  - 审批按钮（通过/驳回）**完全从项目列表移除**，只在审批管理中处理。
  - 操作按钮按角色分支判断，逻辑清晰简洁。
- **关联文件**：`frontend/src/pages/Projects.jsx`（操作按钮区）

#### ④ 项目撤回机制（普通账号）✅
- **需求**：普通账号对自己创建的项目，在待审批/已驳回状态下可撤回，回到 `pending_submit`；撤回不影响 NAS 上已建立的目录和文件。
- **实现**：
  - `backend/app/models.py`：`ApprovalAction` 新增 `submit` 和 `withdraw`；`AuditAction` 新增 `project_withdraw`。
  - `backend/app/routers/projects.py`：新增 `POST /api/projects/{id}/withdraw` 接口；`submit_project` 也写 ApprovalLog。
  - `backend/app/routers/projects.py:update_project`：**放宽**普通账号限制（不再要求"只能编辑自己创建的"），改为"除已通过状态外都可编辑"（用于上传文件）。
  - `backend/app/services/file_storage.py:ensure_webdav_folders`：兼容 NAS 上 PROPFIND/MKCOL 报 405 的情况（视为目录已存在）。
  - `frontend/src/api/index.jsx`：新增 `withdrawProject`。
  - `frontend/src/pages/Projects.jsx`：操作列加「撤回」按钮（仅普通账号 + 自己创建 + pending_approval/rejected）。
- **关联文件**：
  - `backend/app/models.py:ApprovalAction / AuditAction`
  - `backend/app/routers/projects.py:withdraw_project / submit_project / update_project`
  - `backend/app/services/file_storage.py:ensure_webdav_folders`
  - `frontend/src/api/index.jsx:withdrawProject`
  - `frontend/src/pages/Projects.jsx`（操作按钮区）

#### ⑤ 撤回修改模式（ProjectForm withdrawMode）✅
- **需求**：普通账号撤回项目后，进入编辑弹窗应：
  - 标题改为「撤回修改」
  - 项目名称只读（撤回后不可修改），其他字段全部可改 + 可改审批人
  - 底部按钮：「删除项目 / 取消 / 继续编辑（保存修改）」
  - 与普通"仅上传文件"编辑模式区分
- **实现**：
  - `frontend/src/components/ProjectForm.jsx`：新增 `withdrawMode` 和 `onDelete` props。
  - `withdrawMode=true` 时：
    - 标题 = 「撤回修改」
    - 紫色提示：「项目已撤回，可修改除项目名称外的所有字段」
    - 项目信息区显示完整表单（除项目名称只读外，其他都可编辑）
    - 审批人区域可重新选择
    - 底部按钮：[删除项目] [取消] [继续编辑（保存修改）]
  - `frontend/src/pages/Projects.jsx`：判定条件 `pending_submit + 普通账号 + created_by===current_user` 时启用 `withdrawMode`。
  - `onDelete` 回调绑定 `() => handleDelete(editData.id)`（修复了之前 onDelete 没传 id 导致 404 的 bug）。
- **关联文件**：
  - `frontend/src/components/ProjectForm.jsx:withdrawMode / onDelete`
  - `frontend/src/pages/Projects.jsx`（onDelete / withdrawMode 判定）

#### ⑥ 「继续提交」按钮 ✅
- **需求**：撤回并保存修改后，项目回到 `pending_submit` 状态；项目列表应显示「继续提交」按钮，点击后项目进入 `pending_approval`（提交审批）。
- **实现**：
  - `frontend/src/pages/Projects.jsx`：操作列加「继续提交」按钮（仅普通账号 + 自己创建 + `pending_submit` 状态）。
  - `handleSubmit` 增加错误处理（弹窗失败原因）。
- **关联文件**：`frontend/src/pages/Projects.jsx`（操作按钮区 + handleSubmit）

#### ⑦ 创建人列 + 时间精确到分钟 + 北京时区 ✅
- **需求**：
  - 所有项目列表加「创建人」列（放在"填报时间"前面），值为建立项目账号的姓名。
  - 项目管理和审批管理中的填报时间精确到分钟（YYYY-MM-DD HH:mm）。
  - **时间**显示必须是**系统本地时间（北京时区）**，不是 UTC。
- **实现**：
  - `frontend/src/pages/Projects.jsx`：表格加「创建人」列（`p.creator?.real_name`）；时间格式 `YYYY-MM-DD HH:mm`。
  - `frontend/src/pages/Approvals.jsx`：列名「更新时间 → 填报时间」，改用 `created_at`。
  - `frontend/src/pages/UserManagement.jsx`：`toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })`。
  - `frontend/src/pages/AuditLogs.jsx:formatTime`：兼容 UTC 字符串（自动加 Z 后转本地）。
  - **关键修复**：所有页面引入 `dayjs/plugin/utc` 和 `dayjs/plugin/timezone`，用 `dayjs.utc(s).tz('Asia/Shanghai').format(...)` 转换时区（之前 `dayjs(s)` 直接显示会把 UTC 时间当本地显示，导致时间差 8 小时）。
- **关联文件**：
  - `frontend/src/pages/Projects.jsx`（表头 + 列 + 时间格式）
  - `frontend/src/pages/Approvals.jsx`（列名 + 时间字段）
  - `frontend/src/pages/UserManagement.jsx`（时间格式）
  - `frontend/src/pages/AuditLogs.jsx:formatTime`

#### ⑧ 删除项目按钮修复 ✅
- **需求**：在撤回修改模式下的"删除项目"按钮，点了确认后无反应。
- **真因**：`onDelete={handleDelete}` 直接传函数引用，但 `handleDelete(id)` 需要 id 参数，导致 `DELETE /api/projects/undefined` 返回 404。
- **修复**：
  - `frontend/src/pages/Projects.jsx`：`onDelete={() => handleDelete(editData.id)}` 绑定 id。
  - `frontend/src/components/ProjectForm.jsx`：删除按钮加 try/catch + alert，await `onDelete()`。
- **关联文件**：
  - `frontend/src/pages/Projects.jsx:onDelete`
  - `frontend/src/components/ProjectForm.jsx`（删除按钮）

---

### 🗓 2026-08-09（业务需求调整）

#### ① 拼音账号名规则修正（**进行中 / 待优化**）
- **需求**：账号生成规则改为「**名拼音首字母 + 姓拼音全拼**」，例：`人世间 → sjren`、`张三 → szhang`、`李俊峰 → jfli`。
- **当前状态**：
  - 已重写 `backend/app/services/pinyin_util.py:generate_username`，逻辑改为「首字默认作为姓，复姓字典匹配保留」。
  - 已补 `_GIVEN_NAME_PINYIN` 字典里缺失的 `世/间/人/涛/俊/峰/凯/亮/辉/健/雄/豪/玲/慧/洁/宇/宙/洪/波/湖/海/江/河/溪/德/仁/义/礼/智/信/忠/孝/廉/春/夏/秋/冬/东/南/西/北/美/丑/善/恶/爱/恨/喜/怒/哀/乐/悲/思/念/想/梦` 等常用字。
  - 实测结果仍有偏差：`人世间 -> renshijianj`（应为 `sjren`），`刘岩 -> xliu`（应为 `yliu`）。原因：当前算法仍走「从右往左找已知姓」兜底分支，与预期不符。
  - **下一步**：去掉兜底分支，强制「首字 = 姓」。**已暂停，等用户提供明确样例后再继续**。
- **关联文件**：
  - `backend/app/services/pinyin_util.py:generate_username`
  - `backend/app/services/pinyin_util.py:_GIVEN_NAME_PINYIN`

#### ② 申请账号 → 自动返回 8 位随机初始密码 ✅
- **需求**：申请账号时系统生成随机 8 位密码，作为初始密码返回给申请人保存。
- **实现**：
  - `backend/app/routers/auth.py:apply_account`：使用 `secrets.choice(string.ascii_letters + string.digits)` 生成 8 位密码；同步写入 `password_hash`（申请人凭此密码 + 管理员审核通过后即可登录）。
  - `backend/app/schemas.py:ApplyAccountResponse` 新增 `initial_password: Optional[str] = None`。
  - `frontend/src/pages/Login.jsx` 申请成功弹窗：新增「初始密码：」行（红色 `font-mono select-all` 醒目展示）；底部提示改为「请妥善保存初始密码，管理员审核通过后即可用该账号与密码登录系统。」
- **关联文件**：
  - `backend/app/routers/auth.py:apply_account`
  - `backend/app/schemas.py:ApplyAccountResponse`
  - `frontend/src/pages/Login.jsx`（申请结果展示区域）

#### ③ 登录支持账号 或 姓名 登录 ✅
- **需求**：用户可用「账号」或「姓名」登录；登录页占位符改为「请输入账号或姓名」。
- **实现**：
  - `backend/app/routers/auth.py:login`：先按 `username` 精确匹配活跃用户；找不到时按 `real_name` 精确匹配。错误提示改为「账号/姓名或密码错误」。
  - `frontend/src/pages/Login.jsx`：标签 `账号 → 账号 / 姓名`；placeholder `请输入账号 → 请输入账号或姓名`。
- **关联文件**：
  - `backend/app/routers/auth.py:login`
  - `frontend/src/pages/Login.jsx`（登录表单）

#### ④ 用户管理审批弹窗 → 可编辑账号名 ✅
- **需求**：审批待申请账号时，管理员可手动修改系统自动生成的账号名。
- **实现**：
  - `frontend/src/pages/UserManagement.jsx`：
    - `approveForm` 增加 `username` 字段；`openApprove` 时预填（去掉 `!PENDING_` 前缀）。
    - 审批弹窗新增「账号名」输入框（标签带"默认系统生成，可手动修改"提示），取代之前只读展示。
    - `handleApproveSubmit` 把用户编辑后的 `username` 传给 `updateUser`。
- **关联文件**：
  - `frontend/src/pages/UserManagement.jsx:approveForm`
  - `frontend/src/pages/UserManagement.jsx:openApprove`
  - `frontend/src/pages/UserManagement.jsx:handleApproveSubmit`
  - `frontend/src/pages/UserManagement.jsx`（审批弹窗 JSX）

#### ⑤ 角色体系调整：`important_admin → archive`（**此前会话改动**）
- **改动**：
  - `backend/app/models.py:UserRole` 移除 `important_admin`，新增 `archive = "档案管理（只读）"`。
  - 前端 `UserManagement.jsx` 同步：`isImportantAdmin → isArchive`；`ROLE_MAP/ROLE_BADGE` 新增 `archive` 配色（琥珀色 `bg-amber-100 text-amber-700`）。
  - 前端 `Projects.jsx` 增加 `isArchive = role === 'archive'` 分支，仅显示「查看」按钮。
  - 清理 `ProjectForm.jsx` 中残留的 `important_admin` 判断，统一为 `admin`。

#### ⑥ 项目列表多维筛选 + 序号列（**此前会话改动**）
- **改动**：`frontend/src/pages/Projects.jsx`
  - 筛选新增「中标状态 / 金额(万元) 区间 / 填报日期」三个维度。
  - 表格首列加「序号」列 `(page-1)*20 + idx + 1`。

---
