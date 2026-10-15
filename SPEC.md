# 渠道项目登记与审批管理系统 — 规格文档 v1.0

## 1. 项目概览

**项目名称**：渠道项目登记与审批管理系统（Channel Project Management System）
**核心功能**：渠道项目的登记、审批流程、数据汇总与 AI 接入接口
**目标用户**：企业内部渠道管理人员（普通账号 / 重要账号 / 管理员）

---

## 2. 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | React 18 + Vite + TailwindCSS + Shadcn UI + Axios |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.x + Pydantic v2 |
| 数据库 | SQLite（开发）+ PostgreSQL（生产） |
| 文件存储 | Local Storage + WebDAV Client |
| 认证 | JWT（python-jose + passlib） |

---

## 3. 数据库 Schema

### 3.1 用户表 `users`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| username | String(50), UNIQUE | 账号名 |
| password_hash | String(255) | 密码哈希 |
| role | Enum | `admin` / `important` / `normal` |
| real_name | String(100) | 真实姓名 |
| parent_id | Integer, FK(users.id), NULL | 所属重要账号（普通账号时填） |
| is_active | Boolean | 是否启用 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 3.2 项目表 `projects`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| project_name | String(200) | 项目名称 |
| project_code | String(50) | 项目编号 |
| tender_time | Date | 招标时间 |
| bid_time | Date | 投标时间 |
| partner_company | String(200) | 合作单位 |
| cooperation_mode | Enum | `long_term` / `short_term` |
| fee_mode | Enum | `mutual` / `charged` |
| fee_amount | Float, NULL | 收费金额（元） |
| is_sm | Enum | `yes` / `no` |
| project_amount | Float | 项目金额（元） |
| win_bid_status | Enum | `yes` / `no` / `in_progress` |
| tender_file | String(500), NULL | 招标文件路径 |
| bid_file | String(500), NULL | 投标文件存档路径 |
| created_by | Integer, FK(users.id) | 填报人 |
| approver_id | Integer, FK(users.id), NULL | 指定审批人 |
| approval_status | Enum | `pending_submit` / `pending_approval` / `approved` / `rejected` |
| created_at | DateTime | 填报时间 |
| updated_at | DateTime | 更新时间 |

### 3.3 审批日志表 `approval_logs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| project_id | Integer, FK(projects.id) | 关联项目 |
| approver_id | Integer, FK(users.id) | 审批人 |
| action | Enum | `approve` / `reject` |
| comment | Text, NULL | 审批意见 |
| created_at | DateTime | 审批时间 |

---

## 4. API 接口设计

### 4.1 认证模块 `/api/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，返回 JWT |
| POST | `/api/auth/register` | 注册（仅管理员） |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 4.2 用户管理 `/api/users`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users` | 列表（管理员） |
| POST | `/api/users` | 新增用户（管理员） |
| PUT | `/api/users/{id}` | 编辑用户（管理员） |
| DELETE | `/api/users/{id}` | 删除/冻结用户（管理员） |
| PUT | `/api/users/{id}/reset-password` | 重置密码（管理员） |

### 4.3 项目管理 `/api/projects`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 列表（分页+筛选） |
| GET | `/api/projects/{id}` | 详情 |
| POST | `/api/projects` | 新建 |
| PUT | `/api/projects/{id}` | 编辑 |
| DELETE | `/api/projects/{id}` | 删除 |
| POST | `/api/projects/{id}/submit` | 提交审批 |
| POST | `/api/projects/{id}/approve` | 审批通过（重要账号/管理员） |
| POST | `/api/projects/{id}/reject` | 审批驳回（重要账号/管理员） |

### 4.4 数据导出 `/api/export`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/export/projects` | 导出项目 JSON/CSV/Excel |
| GET | `/api/export/llm-summary` | LLM 摘要数据 |

---

## 5. 前端页面结构

| 页面 | 路径 | 权限 |
|------|------|------|
| 登录页 | `/login` | 公开 |
| 项目列表 | `/projects` | 登录后 |
| 新建/编辑项目 | 弹窗 | 登录后 |
| 用户管理 | `/admin/users` | 管理员 |
| 数据汇总 | `/dashboard` | 登录后 |

---

## 6. 目录结构

```
D:\Git\渠道项目登记/
├── SPEC.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       └── projects.py
│   ├── requirements.txt
│   └── config.yaml
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/
        │   └── index.jsx
        ├── pages/
        │   ├── Login.jsx
        │   ├── Projects.jsx
        │   └── UserManagement.jsx
        └── components/
            ├── ProjectForm.jsx
            └── Layout.jsx
```
