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

## 🎯 当前功能模块状态

| 模块 | 状态 | 备注 |
|---|---|---|
| 项目登记 | ✅ 稳定 | 字段级权限 |
| 文件管理 | ✅ 稳定 | 已修 race condition |
| WebDAV | ✅ 稳定 | 兼容空格变体 |
| 申请账号 | ✅ 稳定 | 公开接口 |
| 用户审批 | ✅ 稳定 | 5 个 Tab + 批量操作 |
| 报表 | ✅ 稳定 | Excel 导出 |
| 审计日志 | ✅ 稳定 | 全操作留痕 |

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
6. **commit message 写清楚动机**，不只写"what"

## 🆘 遇到问题先查

1. `backend/uvicorn.err.log` - 后端启动错误
2. `backend/app_debug.log` - 业务日志（含 list-files 的 target_dir）
3. 浏览器 DevTools → Network → 看实际请求和响应
4. `DEBUG_NOTE.md` - 历史 bug 分析（很可能有答案）
5. `git log --oneline -20` - 最近改了什么
