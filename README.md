# 渠道项目登记与审批管理系统

> 一个面向政企/事业单位的渠道项目全生命周期管理平台，支持项目登记、文件归档、审批流转、报表统计、用户管理。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![React](https://img.shields.io/badge/React-18-61dafb)
![Vite](https://img.shields.io/badge/Vite-5-646cff)
![License](https://img.shields.io/badge/License-Internal-lightgrey)

---

## ✨ 主要功能

| 模块 | 功能描述 |
|---|---|
| **项目登记** | 项目名称、类型、金额、合作公司、联系人、预计采购时间等；字段级权限控制（仅创建人、重要管理员、超级管理员可编辑） |
| **文件管理** | 招标资料 / 投标文档双区域，支持拖拽上传、WebDAV 远程存储、文件预览（PDF/Word/Excel/图片/文本）|
| **审批流转** | 多级审批：待审批 → 已通过 / 已驳回；审批意见 + 时间线 |
| **报表管理** | 按用户/项目/时间维度统计；导出 Excel |
| **用户管理** | 4 级角色：系统管理员 / 重要管理员 / 重要账号 / 普通账号；用户审批、批量操作、密码重置 |
| **申请账号** | 公开接口，用户提交姓名 → 自动生成账号（名首字母 + 姓全拼，如 `szhang` / `jfli`）|
| **审计日志** | 登录、增删改、审批、上传、下载等操作全留痕；按时间/操作人/类型筛选 |
| **WebDAV 集成** | 支持远程 NAS（群晖、威联通、自建）文件存储，可配置 SSL/端口/路径 |

---

## 🏗️ 技术栈

**前端**：React 18 + Vite 5 + Tailwind CSS + Ant Design + React Router + Axios  
**后端**：FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2.9 + python-jose JWT + Passlib bcrypt  
**存储**：SQLite（默认）/ MySQL（可换）；本地文件系统 / WebDAV 远程  
**构建**：Vite（前端）+ Uvicorn（后端 ASGI 服务器）

---

## 📁 项目结构

```
channel-project/
├── backend/                      # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 入口 + 路由挂载
│   │   ├── auth.py              # JWT + 密码 hash
│   │   ├── database.py          # SQLAlchemy ORM
│   │   ├── models.py            # 数据库模型
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── routers/             # API 路由
│   │   │   ├── auth.py          # 登录/注册/申请账号
│   │   │   ├── users.py         # 用户管理
│   │   │   ├── projects.py      # 项目 CRUD
│   │   │   ├── approvals.py     # 审批
│   │   │   ├── reports.py       # 报表
│   │   │   ├── audit.py         # 审计
│   │   │   └── file_storage.py  # 文件存储
│   │   └── services/
│   │       ├── webdav_client.py # WebDAV 操作
│   │       ├── file_storage.py  # 本地存储
│   │       ├── pinyin_util.py   # 姓名→账号生成
│   │       └── audit.py         # 审计写入
│   ├── config.example.yaml      # 配置模板（提交）
│   ├── requirements.txt
│   └── start_server.py
├── frontend/                     # React 前端
│   ├── src/
│   │   ├── main.jsx             # 入口
│   │   ├── App.jsx              # 路由
│   │   ├── pages/               # 页面
│   │   │   ├── Login.jsx
│   │   │   ├── Projects.jsx
│   │   │   ├── ProjectForm.jsx
│   │   │   ├── Approvals.jsx
│   │   │   ├── Reports.jsx
│   │   │   ├── FileStorage.jsx
│   │   │   ├── UserManagement.jsx
│   │   │   └── AuditLogs.jsx
│   │   ├── components/          # 公共组件
│   │   ├── api/                 # API 封装
│   │   └── utils/
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── .gitignore
├── README.md
└── DEBUG_NOTE.md                # 调试笔记（仅开发参考）
```

---

## 🚀 快速开始

### 1. 克隆代码

```bash
git clone git@github.com:armyking001/channel-project.git
cd channel-project
```

### 2. 后端启动

```bash
cd backend

# 复制配置模板
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 jwt.secret_key（用 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成）

# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 前端启动

```bash
cd frontend
npm install
npm run dev                     # 开发模式（http://localhost:5173）
# 或
npm run build                   # 生产构建（输出到 backend/static/）
```

### 4. 访问

打开 http://localhost:8000/admin/

- 首次启动自动创建默认管理员账号：`admin` / `Admin@2026`（**请立即修改密码！**）
- 也可通过 `DEFAULT_ADMIN_PASSWORD` 环境变量预置自定义初始密码：

  ```bash
  setx DEFAULT_ADMIN_PASSWORD "YourStrongPassword@2026"  # Windows
  export DEFAULT_ADMIN_PASSWORD="YourStrongPassword@2026"  # Linux
  ```

---

## ⚙️ 配置说明（backend/config.yaml）

```yaml
database:
  url: "sqlite:///./data.db"          # 数据库连接

jwt:
  secret_key: "<必填-随机字符串>"      # 至少 32 字符，生产必须改
  algorithm: "HS256"
  expire_minutes: 1440                # token 有效期（默认 1 天）

webdav:
  enabled: false                     # true=用 NAS, false=用本地磁盘
  base_url: ""                       # 如 https://192.168.1.100:5006
  username: ""
  password: ""                       # 留空则运行时从数据库 FileStorageConfig 读取
  remote_path: "/"

upload:
  local_path: "./uploads"            # 本地存储路径

app:
  host: "0.0.0.0"
  port: 8000
  debug: true
  cors_origins:
    - "http://localhost:5173"
    - "http://127.0.0.1:5173"
```

---

## 🔐 安全要点

1. **`config.yaml` 不提交** — 含 JWT secret + WebDAV 密码；`.gitignore` 已排除
2. **`data.db` 不提交** — 含用户密码 hash
3. **JWT secret 必须随机** — 不能用默认值
4. **生产环境务必**：
   - 关闭 `app.debug`
   - 用强密码
   - 启用 HTTPS
   - 修改默认 admin 密码

---

## 👥 角色权限

| 角色 | 权限 |
|---|---|
| **系统管理员** (`admin`) | 全部权限，包括用户管理、系统配置 |
| **重要管理员** (`important_admin`) | 自己 + 下属 + 上级链 + 所有项目 + 审批 |
| **重要账号** (`important`) | 自己 + 上级链 + 项目 + 审批（可看下属）|
| **普通账号** (`normal`) | 自己的项目 + 自己的上级链 + 自己的报表 |

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📜 许可

仅供内部使用。
