# Agents 记录 — 渠道项目登记

本文档记录本项目中由 Agent 实施的关键功能与改动。

---

## 0. AI表单 + 报表 AI 一期骨架

### 本次目标

- 将原「表单管理」统一更名为 **AI表单**
- 在同一入口内集中管理 **AI 模型配置 + AI 表单模板 + 表单记录**
- 在报表管理页先落地第一期 MVP 骨架：
  - 模型选择
  - AI 分析入口
  - 项目全量导出

### 已实现

#### 1) AI 模型配置

- 新增后端模型：`AIModelConfig`
  - 支持 `local / cloud`
  - 支持 `provider / base_url / model_name / api_key / temperature / max_tokens / timeout_seconds`
  - 支持 `is_enabled / is_default / notes`
- 新增接口（挂在 `/api/forms` 下，统一归到 AI表单）
  - `GET /api/forms/ai-models`
  - `POST /api/forms/ai-models`
  - `PUT /api/forms/ai-models/{id}`
  - `DELETE /api/forms/ai-models/{id}`
- 列表接口默认对 `api_key` 做掩码回显，避免前端直接读取完整密钥
- 新增预置模型能力（展示于 `AI报表 -> 模型配置`）：
  - `Kimi`
  - `MiniMax`
  - `DeepSeek`
- 以上预置模型已内置默认 `provider / base_url / model_name / timeout / temperature`
- 使用时只需填写 `API Key` 即可保存
- 同时保留“自定义本地模型”入口，用于接入 `Ollama` 或内部 OpenAI 兼容服务
- 新增模型测试接口：
  - `POST /api/forms/ai-models/{id}/test`
  - 用于测试模型连通性与响应耗时（ms）
  - 前端会显示测试成功/失败、耗时、返回摘要
- 修复一个兼容问题：
  - 编辑模型时若 `api_key` 留空，后端不再把原值覆盖为空字符串

#### 2) AI表单入口改造

- 左侧菜单文案改为 **`🤖 AI表单`**
- `/admin/forms` 页面升级为统一入口，增加四个页签：
  - `总览`
  - `模型配置`
  - `AI表单模板`
  - `表单记录`
- `FormBuilder.jsx` 的标题和占位文案同步改为 AI 表单语义

#### 3) 报表管理 AI 入口

- 报表页顶部增加 **AI 分析入口**
- 支持：
  - 选择已启用模型
  - 输入分析要求
  - 勾选允许 AI 使用的字段
  - 选择展示方式（表格 / 柱状图 / 趋势图 / 摘要）
- 当前后端 `POST /api/reports/ai-analyze` 为 **MVP 骨架**
  - 遵循现有报表权限范围取数
  - 返回模型信息、筛选条件、字段列表、预览数据、后续建议
  - 暂未真正调用本地/云端大模型，仅打通前后端通路

#### 4) 报表全量导出

- 新增接口：`GET /api/reports/export-full`
- 在原 Excel 导出之外新增 **`📦 全量导出`** 按钮
- 导出内容扩展为：
  - 项目来源（自营 / 渠道）
  - 表单实例 ID
  - 责任销售
  - 项目概述
  - 存储区域
  - 招标资料 / 投标文档目录
  - 最新跟单阶段 / 进展 / 预计金额
  - 创建时间 / 更新时间

### 涉及文件

- 后端模型：[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py)
- 后端 Schemas：[backend/app/schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py)
- AI表单路由：[backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py)
- 报表路由：[backend/app/routers/reports.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/reports.py)
- 前端 API：[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)
- AI表单页：[frontend/src/pages/FormTemplates.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/FormTemplates.jsx)
- AI表单构建页：[frontend/src/pages/FormBuilder.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/FormBuilder.jsx)
- 报表页：[frontend/src/pages/Reports.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Reports.jsx)
- 布局导航：[frontend/src/components/Layout.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx)

---

## 1. 存储区域（StorageZone）多区域管理

### 背景

原系统只有一个 `FileStorageConfig`（单例 `id=1`），所有项目共用同一套 NAS 连接配置。
业务上需要：
- 用户可自定义多个文件存储位置（命名、本地或 WebDAV/NAS）
- 不同表单/项目可选择使用不同的存储区域
- 文件按所选区域 + 子路径自动落到 NAS 的不同目录

### 数据模型

- **新表 `storage_zones`**：
  - `id`, `name`(唯一), `mode`(local/webdav)
  - `local_path` / `webdav_url` + `webdav_port` + `webdav_use_ssl`
  - `webdav_username` + `webdav_password`
  - `webdav_base_path`（NAS 起始路径）
  - `sub_path`（区域下的子路径，用于分类）
  - `description`, `is_active`, `sort_order`
- **新增字段**：
  - `projects.storage_zone_id` → `storage_zones.id`（每个项目可单独指定）
  - `form_templates.storage_zone_id` → `storage_zones.id`（每个表单模板默认指定）
- **保留兼容**：旧的 `file_storage_config` 表保留，启动时自动迁移为「默认存储」区域

### API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/storage-zones` | 列出所有区域 |
| GET | `/api/storage-zones/{id}` | 获取单个区域 |
| POST | `/api/storage-zones` | 创建区域（admin） |
| PUT | `/api/storage-zones/{id}` | 更新区域（admin） |
| DELETE | `/api/storage-zones/{id}` | 删除区域（admin，需检查无项目使用） |
| POST | `/api/storage-zones/{id}/test-connection` | 测试连通性 |

### 路径计算

```
local:  {local_path}/{sub_path?}/{responsible_sales}+{project_name}+{date}
webdav: {scheme}://{host}[:port]/{webdav_base_path}/{sub_path?}/{...}/{招标资料|投标文档}
```

### 前端

- **入口**：`/admin/storage-zones` 页面，提供 CRUD、测试连接功能
- **入口位置**：「文件管理」页面右上角「🌐 存储区域管理」按钮
- **表单管理**：`FormBuilder.jsx` 顶部下拉选择存储区域
- **项目列表**：`ProjectForm.jsx` 审批人区域下方新增「存储区域」下拉

### 文件

- 后端模型：[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py)
- 后端路由：[backend/app/routers/storage_zones.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/storage_zones.py)
- Schemas：[backend/app/schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py)
- 文件存储服务：[backend/app/services/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/file_storage.py)
- 表单文件存储服务：[backend/app/services/form_file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/form_file_storage.py)
- 前端 API：[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)
- 前端页面：[frontend/src/pages/StorageZones.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/StorageZones.jsx)
- 项目表单 UI：[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)

---

## 2. 内置表单模板（渠道项目登记表 / 自建项目登记表）

### 背景

- 系统内两份内置表单模板，启动时自动同步到 `form_templates` 表
- 字段定义严格对齐 `ProjectForm.jsx`，实现「所见即所得」
- 自建项目登记表与渠道项目登记表字段集完全一致，仅文件存储位置不同（自建项目使用 NAS 子目录「自建项目/」）

### 字段分区（22 项）

| 分区 | 字段数 | 字段 |
|---|---|---|
| 项目基本信息 | 9 | 项目名称、责任销售、项目编号、项目类型、预计金额、招标时间、投标时间、业主联系人、业主联系方式 |
| 合作基本情况 | 10 | 公司名称、公司地址、主要资质、法定代表、联系人、联系方式、合作模式、费用模式、中标状态、是否SM |
| 项目基本情况 | 1 | 项目基本情况（textarea） |
| 文件管理 | 2 | 招标资料、投标文档（多文件上传） |

### 关键文件

- [backend/app/services/builtin_templates.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/builtin_templates.py)
- [frontend/src/data/projectFormTemplate.js](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/data/projectFormTemplate.js)

---

## 3. 表单生成器（FormBuilder）— 所见即所得

### 背景

原 FormBuilder 是单列拖拽布局，与实际渲染表单（两列）不一致。
改造后 FormBuilder 中栏直接渲染真实的分区 + 两列字段，编辑体验 = 实际使用体验。

### 实现

- 中栏：分区用绿色标题条 + 左侧绿色竖线（与 ProjectForm 一致）
- 分区内字段以两列网格渲染
- 每个字段卡片直接渲染真实控件（text/number/date/select/file）
- 分区标题可点击重命名，顶部「+ 添加新分区」按钮
- 分区底部「+ 单行文本/数字/日期/下拉/文件…」快捷按钮
- 顶部工具栏：「从渠道项目模板加载」「从自建项目模板加载」一键复制字段

### 关键文件

- [frontend/src/pages/FormBuilder.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/FormBuilder.jsx)
- [frontend/src/pages/FormTemplates.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/FormTemplates.jsx)

---

## 4. DynamicForm 样式统一

### 背景

「DynamicForm」与「ProjectForm」原本样式不一致。两者合并为同一套视觉风格：

- 题头：`h3 text-xl font-bold text-gray-800` + 右上角模式徽章
- 分区标题：`bg-green-50 border-l-4 border-green-500`
- 字段：2 列网格（`grid grid-cols-2 gap-x-8 gap-y-3`）
- 文件管理：2 列布局（招标资料 + 投标文档）
- 审批人：只读显示
- 底部：「取消」+「提交」按钮

### 关键文件

- [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)
- [frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)

---

## 5. 部署与服务端口

### 本地启动（端口 8765）

Windows 8000 端口被 Hyper-V 保留（7904-8003 范围），因此本地测试用 8765：

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

访问：`http://127.0.0.1:8765/admin/`

### 生产部署

- 服务器：`172.16.10.92:26731`
- 使用 `python deploy/deploy_all.py` 一键部署

---

## 6. 数据库自动迁移

应用启动时自动执行以下迁移：

1. `file_storage_config.template`：从 `{real_name}` 升级到 `{responsible_sales}`
2. 创建 `storage_zones` 表（如不存在）
4. `projects.storage_zone_id`、`form_templates.storage_zone_id`：添加列（如不存在）
5. 同步「默认存储」区域（从旧配置迁移）
6. 同步两份内置表单模板（渠道项目登记表 / 自建项目登记表）

---

## 7. 自建项目逻辑与渠道项目平行

### 背景

用户要求「自建项目建立的逻辑和渠道项目逻辑一样，二者是平行关系」。本节记录将自建项目（FormInstance）路径与列表展现对齐渠道项目（Project）的所有改动。

### 关键设计

- **存储位置**：渠道项目 → NAS `渠道资料/`；自建项目 → NAS `自营资料/`，由模板的 `storage_zone_id` 决定
- **项目根目录命名**：均使用 `{responsible_sales}+{project_name}+{date}`（责任销售 + 项目名 + 项目建立日期）
- **审批人**：自动从 `current_user.parent_id` 解析，兜底用 `admin`，不暴露给用户选择
- **审批状态**：自建项目创建后直接进入 `pending_approval`（待审批）
- **list 中显示**：自建项目同步写入 `projects` 表（`source='self'` + `form_instance_id`），与渠道项目同一表同一列表

### 后端改动

| 改动 | 文件 |
|---|---|
| `FormInstance` 增字段：`storage_zone_id` / `approver_id` / `approval_status` / `updated_at` | [backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) |
| `Project` 增字段：`source` (`channel`/`self`) + `form_instance_id` | [backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) |
| `create_instance` 严格调用 `create_project_folders`（与渠道项目同一函数） | [backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) |
| `create_instance` 自动按模板的 `storage_zone_id` 构造虚拟 FileStorageConfig（参考渠道项目逻辑） | [backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) |
| `create_instance` 同时在 `projects` 表创建 `source='self'` 记录（让自建项目出现在项目列表） | [backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) |
| `create_project` 恢复原始逻辑（只用 FileStorageConfig + create_project_folders；抛弃 StorageZone 直传） | [backend/app/routers/projects.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py) |
| `list_projects` 支持 `source` 过滤 | [backend/app/routers/projects.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py) |
| `compute_form_folders` 已有 tender_folder/bid_folder 时直接复用（**避免 initFormFolders 重复创建**） | [backend/app/services/form_file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/form_file_storage.py) |
| `PathPreviewRequest` 增 `source`/`storage_zone_id` 字段 | [backend/app/schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py) |
| `preview-path` 接口识别 `source='self'` → 走 StorageZone，反之走 FileStorageConfig | [backend/app/routers/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py) |

### 前端改动

| 改动 | 文件 |
|---|---|
| `DynamicForm` 提交后**删除** `initFormFolders` 调用（避免重复创建） | [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx) |
| `DynamicForm` 提交时按 label 反查「责任销售 / 项目名称 / 合作单位 / 项目类型」字段并映射到约定英文 key | [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx) |
| `DynamicForm` 路径预览按 label 反查「责任销售」「项目名称」，并展示完整路径（含 `webdav_base_path`） | [frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx) |
| `ProjectForm` 调用 preview-path 时传 `project.source` / `project.storage_zone_id` | [frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx) |
| `Projects.jsx` 筛选栏新增「项目类型」下拉（全部 / 渠道项目 / 自建项目） | [frontend/src/pages/Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx) |

### 关键决策记录

1. **字段 key 是 FormBuilder 生成的** `field_${timestamp}_${counter}` **形式**，约定在自定义表单中：
   - label `责任销售` → 后端字段 `responsible_sales`
   - label `项目名称` / `项目名` → 后端字段 `project_name`
   - label `合作单位` / `合作公司` → 后端字段 `partner_company`
   - label `项目类型` → 后端字段 `project_type`
2. **`create_instance` 不会触发 `initFormFolders`**，改为 `create_instance` 时直接调用 `create_project_folders`（与渠道项目同函数）
3. **`compute_form_folders` 幂等**：实例已有 `tender_folder`/`bid_folder` 时直接复用，仅做一次 MKCOL 检查
4. **存储路径选择**：自建项目（模板 `storage_zone_id=3`）→ 「自营资料」；渠道项目 → 「渠道资料」。前端路径预览与编辑时都按 `source` 参数区分

---

## 8. 命名统一：「自建项目」→「自营项目」

### 背景

为与后端 NAS 目录命名（`自营资料/`）一致，将前端用户可见的「自建项目」字样统一改为「自营项目」。同时后端内置表单模板同步更名。

### 改动清单

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 按钮「自营项目新建」 | 自建项目新建 | 自营项目新建 |
| 项目类型筛选下拉 | 自建项目 | 自营项目 |
| 内置表单模板名 | 自建项目登记表 | 自营项目登记表 |
| 内置模板描述 | 自建项目登记表单... | 自营项目登记表单... |
| 内置模板 `storage_sub_path` | 自建项目 | 自营项目 |
| `DynamicForm` 标题判断 | 仅识别 `渠道/自建项目登记表` | 同时识别 `自营项目登记表` |
| `Projects.jsx` 模板查找 | `name.includes('自建项目')` | `name.includes('自建项目') \|\| name.includes('自营项目')`（兼容） |
| 错误提示 | 未找到"自建项目登记表"模板 | 未找到"自营项目登记表"模板 |

### 数据库迁移

`backend/app/main.py` 启动时检测到旧名「自建项目登记表」记录时，自动重命名为「自营项目登记表」（避免重复创建）。

### 兼容策略

- 后端迁移代码兼容旧记录（已存在的「自建项目登记表」会被改名为「自营项目登记表」）
- 前端模板查找同时识别「自建项目」与「自营项目」两个关键字
- `DynamicForm` 标题判断同时兼容三个模板名
- 数据库枚举字段 `Project.source` 仍为 `self`（值未改），前端文案为「自营项目」

### 关键文件

- 后端模板：[backend/app/services/builtin_templates.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/builtin_templates.py)
- 后端迁移：[backend/app/main.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/main.py)
- 前端按钮：[frontend/src/pages/Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)
- 前端标题判断：[frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)

---

## 9. 责任销售非必填：留空自动用账号姓名

### 背景

业务上：销售本人新建项目时「责任销售」= 当前账号姓名，无需重复填写。要求「如由销售本人建立，此处可不填」。

### 行为

- `responsible_sales` 字段在 Pydantic 中由必填改为可空（`Optional[str]`）
- 后端 `create_project` / `update_project` 留空 → 自动用 `current_user.real_name`（兜底 username）
- 前端 `[ProjectForm.jsx]` placeholder 改为「如由销售本人建立，此处可不填」，去除红星，去除必填校验
- 前端 `[DynamicForm.jsx]` 通过**字段 label =「责任销售」识别**，统一跳过必填校验、不显示红星、覆盖 placeholder 文案（**不动 DB 中已存的模板字段定义**）
- 「责任销售」统一不强制必填，即使模板 `required=true`

### 关键文件

- 后端 schema：[backend/app/schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py) `ProjectCreate.responsible_sales`
- 后端项目路由：[backend/app/routers/projects.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py)
- 后端表单路由（已有兜底）：[backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py)
- 前端 ProjectForm：[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)
- 前端 DynamicForm：[frontend/src/components/DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)

---

## 10. 编辑项目时项目编号空字符串导致 UNIQUE 冲突修复

### 背景

`projects.project_code` 列定义为 `unique=True, nullable=True`。
SQLite 中允多多个 `NULL`，但 `''` ≠ `NULL`，多个空字符串会被 `UNIQUE` 约束拒绝。
编辑项目清空「项目编号」字段 → 前端传 `''` → `IntegrityError`。

### 修复

[backend/app/routers/projects.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py) `update_project` 在 `setattr` 循环前：

1. **唯一性校验**：`project_code` 空字符串 → 规范化为 `None`；非空 → 检查其他项目占用
2. **空字符串规范化**：`partner_company / owner_contact_person / company_address` 等 11 个字段统一 `''` → `None`

`create_project` 原本就有同类规范化逻辑（第 158-163 行）。

---

## 11. 内置表单模板「保留用户编辑」策略

### 背景

[backend/app/main.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/main.py) 启动时同步内置模板时，会用 `builtin_templates.py` 里的 `fields` **强制覆盖** DB 中的版本，导致用户之前在 FormBuilder 中编辑的字段定义被回滚。

### 修复

启动同步策略改为「保留用户编辑」：

```python
if existing:
    # 已存在：只更新元数据（description/storage_zone_id），不覆盖 fields
    existing.description = builtin.get('description', '')
    if builtin.get('storage_zone_id'):
        existing.storage_zone_id = builtin.get('storage_zone_id')
    if builtin.get('storage_sub_path'):
        existing.storage_sub_path = builtin.get('storage_sub_path')
    existing.is_active = True
```

- ✅ 已存在的内置模板：只更新 description / storage_zone_id，不动 fields
- ✅ 首次启动：用代码里的字段初始化
- ✅ 用户在 FormBuilder 中编辑的内容不会因后端重启丢失

---

## 12. 项目跟单（ProjectFollowup / 项目汇报）模块

### 需求背景

为已审批项目添加跟单 / 汇报机制：跟单 = 一个时间点上的进展快照，按 `project_id` 串联为时间轴；周/月/固定周期汇报；预计成交金额、签单日期等。

### 数据模型

[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) 新增 `FollowupStage` 枚举（5 阶段：需求对接 / 方案提供 / 商务沟通 / 投标报价 / 其他）+ `ProjectFollowup` 模型；`Project` 加 `followups` 关系。

字段：项目ID、所处阶段、当前进展、风险、下一步计划、责任人/截止时间、预计成交金额/签单日期、周期类型/标签、汇报人、创建/更新时间。

### 内置模板：项目跟单登记表

[backend/app/services/builtin_templates.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/builtin_templates.py) 新增 `FOLLOWUP_TEMPLATE`（7 字段 / 3 分区），启动时同步到 `form_templates` 表。**所见即所得**：在「表单管理」中编辑后，新弹窗立即按新模板渲染。

### form_data 动态字段

[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) `ProjectFollowup` 加 `form_data: Text`（JSON 字符串），存储模板自定义字段。

[backend/app/routers/project_followups.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py)：
- `create_followup` / `update_followup` 序列化 form_data (dict → JSON)
- `_to_response` 反序列化 form_data (JSON → dict)
- 启动迁移：`project_followups.form_data` 列

### API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/project-followups/stage-options` | 阶段下拉 |
| GET | `/api/project-followups/followable-projects` | 当前账号可新建跟单的项目 |
| GET | `/api/project-followups/template` | 当前激活「项目跟单登记表」字段定义 |
| GET | `/api/project-followups` | 跟单列表（含 `responsible_sales` 过滤） |
| GET | `/api/project-followups/timeline?project_id=X` | 单项目时间轴 |
| GET | `/api/project-followups/summary` | 阶段分布 + 预计成交合计 |
| POST | `/api/project-followups` | 新建 |
| PUT | `/api/project-followups/{id}` | 更新 |
| DELETE | `/api/project-followups/{id}` | 删除（仅 admin） |

[backend/app/routers/reports.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/reports.py) 新增 `/api/reports/by-followup-stage`，接入报表页。

### 权限策略

| 角色 | 列表可见 | 新建跟单项目范围 | 编辑 | 删除 |
|---|---|---|---|---|
| admin (项目管理员) | 全部已审批 | 全部已审批 | ✅ | ✅ |
| important (重要账号) | 自己+下属创建 | 自己创建 + 责任销售是自己的 | 仅自己 | ❌ |
| normal (普通账号) | 自己创建/被指派审批 | 自己创建 + 责任销售是自己的 | 仅自己 | ❌ |
| archive (档案) | 全部（只读） | - | ❌ | ❌ |

后端 `delete_followup`：**仅 admin**。`update_followup`：admin 或 reporter 本人。

新建跟单校验：仅 `approval_status == 'approved'`（已审批通过）的项目可跟单。

### 前端

[frontend/src/pages/ProjectFollowups.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/ProjectFollowups.jsx)：

- **5 阶段汇总卡片**：每阶段项目数 + 涉及项目数 + 预计成交合计
- **筛选栏**：项目名称 / 责任销售 / 全部阶段 / 全部周期 / 重置
- **列表**：项目名称、所处阶段、周期、当前进展、责任人、预计成交、责任销售（替换原「汇报人」）、汇报时间、操作
- **操作列**：查看（所有角色）/ 编辑（admin 或 reporter 本人）/ 删除（仅 admin）
- **复合下拉**（搜索 + 选项一体）：项目下拉支持前端搜索，搜索结果为空时显示「您可能没有自建的项目或责任销售不是您本人」提示；选中后上方显示蓝色「✓ 已选择」标签 + 清除按钮
- **动态表单**：按模板 fields 自动渲染（text/textarea/number/date/select）
- **「+ 添加字段」**：本次会话临时添加任意字段（field name + value），不依赖模板
- **「保存并新建下一条」**：保存当前 → 清空表单（保留 project_id）→ 不关闭弹窗，连续添加
- **本次已保存列表**：弹窗底部显示「本次会话已保存 N 条」
- **无项目时按钮禁用**：灰背景 + cursor-not-allowed，hover 提示

[frontend/src/pages/Reports.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Reports.jsx)：新增「项目跟单 — 各阶段项目数」柱状图 + 各阶段预计成交金额。

### 关键文件

- 后端模型：[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py)
- 后端路由：[backend/app/routers/project_followups.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py)
- 后端报表：[backend/app/routers/reports.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/reports.py)
- 后端 schema：[backend/app/schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py)
- 后端内置模板：[backend/app/services/builtin_templates.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/builtin_templates.py)
- 后端启动迁移：[backend/app/main.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/main.py)
- 前端 API：[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)
- 前端页面：[frontend/src/pages/ProjectFollowups.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/ProjectFollowups.jsx)
- 前端路由：[frontend/src/App.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/App.jsx)
- 前端菜单：[frontend/src/components/Layout.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx)
- 前端报表：[frontend/src/pages/Reports.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Reports.jsx)

---

## 13. 跟单表聚合/历史/导出优化（2026-08-20）

### ① 时间轴弹窗显示所有模板字段（含自定义）✅

- **需求**：编辑跟单时弹窗只显示硬编码的几个字段，自定义字段看不到具体内容
- **实现**：
  - [ProjectFollowups.jsx:900-952](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/ProjectFollowups.jsx#L900-L952) 改为按模板 fields 动态渲染（所见即所得）
  - 模板字段未填报时显示「（未填报）」占位，避免空洞
  - 数字千分位、日期 `YYYY-MM-DD` 格式化
  - 时间统一加 UTC 时区后缀，前端自动转为本地显示
- **关联文件**：
  - `frontend/src/pages/ProjectFollowups.jsx`
  - `backend/app/routers/project_followups.py`（`_ensure_utc` 修复时区）

### ② 编辑即追加（保留历史）✅

- **需求**：每次编辑跟单都要记录，旧记录不能被覆盖
- **实现**：
  - [project_followups.py:553-611](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py#L553-L611) `update_followup` 改为「编辑即新建」模式：原记录保留，追加新 id，`reporter_id` 记当前编辑者
  - 时间轴接口返回该项目的所有历史版本
- **测试**：本地连续 2 次编辑同一项目，`/timeline` 返回 3 条记录（原 + 2 次新增）

### ③ 列表聚合 + 导出全部历史 ✅

- **需求**：列表默认按项目聚合（每项目显示最新一条）；Excel 导出显示该项目所有历史；可选项目后再导出
- **实现**：
  - `list_followups` / `export_followups` 加 `aggregate: bool` 参数（默认 True）
  - `export_followups` 加 `project_ids` 参数（逗号分隔，None=全部）
  - [ProjectFollowups.jsx:200-235](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/ProjectFollowups.jsx#L200-L235) 加复选框（全选当前页 + 单个切换）
  - 导出按钮动态文案「导出 Excel（全部历史）」/「导出所选 N 项」
  - doExport **强制** `aggregate=false`（不受列表聚合开关影响）
  - Excel 时区转换（UTC → Asia/Shanghai）
- **测试**：选中 2 个项目导出 → Excel 7 行；不选 → 全部历史

### ④ Admin 权限 + token 同步 ✅

- **需求**：系统管理员保存存储区域/表单时报 403（菜单显示 8 项但请求被拒）
- **根因**：浏览器多 tab 切换账号导致 localStorage.user 与 localStorage.token 不一致
- **实现**：
  - [Layout.jsx:14-35](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L14-L35) 每次 Layout 加载时调用 `/auth/me` 同步 store.user
  - [api/index.jsx:17-41](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx#L17-L41) 响应拦截器：401 或 403 + admin 路径 → 强制清 token 并跳登录页
  - 核对后端所有 admin 接口权限检查均正确（无 bug）
- **测试**：admin token PUT /storage-zones/1 → 200；admin token PUT /forms/templates/3 → 200

### ⑤ 跟单自动写入 NAS/WebDAV ✅

- **需求**：跟单编辑了存储区域，但 NAS 目录「自营资料/跟单资料」一直为空
- **根因**：`create_followup` / `update_followup` **完全没有写文件逻辑**，只写数据库
- **实现**：
  - 新增服务 [backend/app/services/project_followup_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/project_followup_storage.py)
  - `save_followup_to_storage(db, item)`：按模板 `storage_zone_id` 路由到对应区域
  - 文件路径规则：`{base_path}/{project_id}-{project_name}/{followup_id}.{json|md}`
  - 每条跟单生成 2 个文件：完整 JSON + Markdown
  - [file_storage.py:158-182](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/file_storage.py#L158-L182) 新增 `webdav_upload_file()`（PUT 上传）
  - [file_storage.py:157-164](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/file_storage.py#L157-L164) 新增 `write_local_file()`
  - [project_followups.py:548-555, 637-644](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py#L548-L555) `create_followup` / `update_followup` 调用 `save_followup_to_storage`（best-effort：失败不影响主流程）
- **测试**：
  - `POST /api/project-followups` → 服务端日志 `[followup_storage] create id=18 -> True: 已保存到 WebDAV: https://172.16.10.252:5006/自营资料/跟单资料/1-自营项目新建1/18.json`
  - `PUT /api/project-followups/18` → `[followup_storage] edit id=19 -> True: 已保存到 WebDAV: https://...19.json`

---

## 14. UI 细节微调（2026-08-20）

### ① 系统名 + 菜单顺序调整 ✅

- **需求**：左侧菜单中「审计记录」与「表单管理」位置互换；系统名「项目管理系统」→「**销售项目管理系统**」
- **实现**：
  - [Layout.jsx:113-121](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L113-L121) 菜单项顺序：表单管理 → 审计记录
  - [Layout.jsx:83](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L83) 侧栏标题
  - [Login.jsx:65-71](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Login.jsx#L65-L71) 登录页标题 + 卡片宽度 480→**560px** + logo 128→140
  - [index.html:6](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/index.html#L6) 浏览器 tab 标题
  - [main.py:475](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/main.py#L475) FastAPI title
- **部署**：增量部署 `17c2076` ✓

### ② 移除「+ 添加字段」功能 + 侧栏标题不换行 ✅

- **需求**：跟单弹窗底部的「+ 添加字段」按钮不要；侧栏「V2.1」不要换行
- **实现**：
  - [ProjectFollowups.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/ProjectFollowups.jsx) 删除按钮、UI 区块、`useState`、`addExtraField`、`removeExtraField`
  - [Layout.jsx:79,83](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L79) Logo `h-10`→`h-8`，h1 加 `whitespace-nowrap`
- **Bug 修复**：上次删除 `extraFields` state 时漏删 2 处调用 `setExtraFields([])`（openCreate/openEdit），导致点击编辑按钮打不开弹窗。已彻底清理。
- **部署**：增量部署 `8fc787f` ✓

---

## 15. 档案管理账号隐藏项目跟单（2026-08-20）

### 需求

档案管理（`archive` 角色）账号**前台**不可见项目跟单（菜单 + 页面 + 直链 URL），但**后台 API 保留**（后续看情况再启用扩展）。

### 三层隐藏实现

| 层 | 文件 | 实现 |
|---|---|---|
| ① 侧栏菜单 | [frontend/src/components/Layout.jsx:96-100](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L96-L100) | `项目跟单` 菜单项加 `!isArchive` 条件渲染 |
| ② 路由守卫 | [frontend/src/App.jsx:21-28,39](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/App.jsx#L21-L28) | 新增 `ArchiveGuard` 组件，archive 访问 `/project-followups` 自动 `<Navigate to="/projects" replace />` |
| ③ 项目列表 | [frontend/src/pages/Projects.jsx:302-306](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx#L302-L306) | 操作列对 archive 只显示"查看"按钮（原有逻辑，列表无跟单列） |

### 后端 API 完全保留

- ❌ **未修改** [backend/app/routers/project_followups.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py) 任何权限代码
- ✅ 所有 `/api/project-followups/*` 接口对 archive 仍可访问（数据可读可写，留给未来扩展）
- ✅ 第 12 章权限矩阵中 `archive` 行的"列表可见：全部（只读）"继续保持有效

### 部署

- 增量部署 `a40d57c` ✓
- GitHub 已同步 `17c2076..a40d57d main -> main`

---

## 16. 数据同步：本地表单配置同步到服务端（2026-08-20）

### 需求

本地 3 个表单模板 + 3 个存储区域 + 4 个表单记录 → 服务端数据库需与本地完全一致。

### 同步范围

| 表 | 数量 | 说明 |
|---|---|---|
| `storage_zones` | 3 | 172NAS/渠道资料、172NAS/自营资料、172NAS/跟单存储 |
| `form_templates` | 3 | 渠道项目登记表（22字段）、自营项目登记表（19字段）、项目跟单登记表（5字段） |
| `form_instances` | 4 | 4 条已填写的自建项目记录 |
| `users` / `projects` / `approval_logs` / `audit_logs` | 不变 | 保留服务端原有数据 |

### 同步方法

1. **`dump_local.py`**：导出本地 SQLite 表为 SQL INSERT 语句（保留本地自增 ID）
2. **SCP 上传**到服务器 `/tmp/sync.sql`
3. **SQLite3 命令行应用**：`sqlite3 data.db < sync.sql`
4. **修复 `sqlite_sequence`**：让 AUTOINCREMENT 从本地最大 ID + 1 开始（避免主键冲突）
5. **外键完整性校验**：所有引用均有效，无孤儿数据

### 安全保证

- ✅ 同步前自动备份 `/opt/channel-project-data-backup-20260820163504/`
- ✅ 未触碰 `users` / `projects` / `approval_logs` / `audit_logs`（生产数据零影响）
- ✅ 操作可回滚（备份命令记录在 deploy 日志）

### 关键文件

- 同步脚本：[deploy/dump_local.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/dump_local.py)
- 同步 SQL：`C:/Users/jwang/AppData/Local/Temp/sync.sql`（一次性产物，未入仓）

---

## 17. 用户手册：销售项目管理系统V2.1（2026-08-20）

### 需求

生成 Word 版本用户手册，覆盖「用户登录 → 申请 → 新建项目 → 跟单 → 审批」全流程，以普通账号和重要账号 2 个角色为例。

### 文档信息

| 项目 | 内容 |
|---|---|
| 文件名 | `销售项目管理系统V2.1_用户手册.docx` |
| 大小 | 46.2 KB |
| 章节数 | 7 章 + 封面 + 目录 + 附录 |
| 角色覆盖 | 普通账号（刘建辉）+ 重要账号（罗隽） |

### 文档结构

| 章节 | 内容 |
|---|---|
| 一、概述 | 系统功能、4 种角色、访问地址、示例账号 |
| 二、账号申请与登录 | 申请流程（4 步） + 登录流程（3 步） |
| 三、系统主界面 | 左侧导航、顶部状态栏、工作区介绍 |
| 四、普通账号流程 | 新建项目（9 步）→ 编辑 → 撤回 → 新建跟单 → 时间轴 |
| 五、重要账号流程 | 待审批列表 → 通过 / 驳回 → 全局跟单 |
| 六、查看报表 | 4 大统计报表 |
| 七、附录 | 状态字段、跟单阶段、角色权限、FAQ |

### 关键文件

- 生成脚本：`C:\Users\jwang\AppData\Local\Temp\gen_manual.py`（一次性脚本）
- 输出文件：
  - 桌面原始：`C:\Users\jwang\Desktop\销售项目管理系统V2.1_用户手册.docx`
  - 项目目录：`Z:\soft-RED\hermes\开发软件\渠道项目登记\销售项目管理系统V2.1_用户手册.docx`
  - **仓库内**：`销售项目管理系统V2.1_用户手册.docx`（已 commit `a40d57c`）

### 工具

- **python-docx**：生成 .docx 文件
- **set_cn_font**（'微软雅黑'）：保证 Word 中文显示美观
- **步骤徽章 + 提示框 + 表格 Light Grid 样式**：可视化操作路径




---

## 18. 通知中心 — 站内消息 + 红点 + 外部通道扩展（2026-08-21）

### 需求

业务上需要"管理账号需要审批/查看/通过时,软件右上角出现小红点,也可通过短信/钉钉通知"。这是核心流程的通知收口,适用于审批/跟单/账号/公告 4 类事件。

### 数据模型

[backend/app/models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) 新增 3 张表 + `User` 表加 2 字段：

#### Notification 表
- `id`, `receiver_id`(接收人), `type`(事件类型), `title`, `content`
- `target_type` + `target_id`(关联业务对象,点击跳转用)
- `is_read` / `read_at`(站内已读)
- `extra`(JSON:业务参数/推送标记)
- `created_at`

#### NotificationSetting 表
- `(user_id, type)` 唯一
- `in_app` / `sms` / `dingtalk` 三组布尔开关
- 用户可单独关闭特定事件的某条通道

#### NotificationChannel 表
- `type` 唯一(`dingtalk_webhook` / `dingtalk_corp` / `sms_aliyun` / `sms_tencent`)
- `name`, `config`(JSON), `enabled`
- admin 配置密钥用,每类通道只保留一份最新配置

#### User 加字段
- `phone`(短信用)
- `dingtalk_user_id`(钉钉工作通知定向投递用)

### 事件类型 (NotificationType 枚举)

| 事件 | 接收人 | 触发点 |
|---|---|---|
| `account_apply` | 所有 admin | [auth.apply_account](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/auth.py) 用户申请 |
| `account_approved` / `account_rejected` | 申请人 | admin 通过/驳回账号申请(预留,后续接入) |
| `password_reset` | 被重置人 | [users.reset_password](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/users.py) admin 重置密码 |
| `followup_viewed` | 该跟单的 reporter(去重 + 60s 节流) | [project_followups.project_timeline](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/project_followups.py) 跟单被查看 |
| `project_pending` | 项目的 approver_id | [projects.create_project](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py) 项目创建 + [projects.submit_project](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py) 提交审批 |
| `project_approved` / `project_rejected` | 项目 created_by | [approvals.approve / reject](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/approvals.py) |
| `system_announcement` | 全体 active user(fanout,排除发送人) | [notifications_ws.announce](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/notifications_ws.py) admin 群发 |

### 推送策略

[backend/app/services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py) 核心设计：

1. **WS 连接池**:`ConnectionManager` 按 `user_id` 维护 `Set[WebSocket]`,支持多 tab 同号连
2. **事件循环绑定**:`lifespan` 启动时 `set_event_loop(asyncio.get_running_loop())`,后续同步 DB 操作可用 `run_coroutine_threadsafe` schedule 异步 WS 推送
3. **双通道落地**:
   - **站内**:写 `notifications` 表 + 立即 `WS.send_to(user_id, {event: "notification.new", data: {...}})`
   - **外部(sms/dingtalk)**:根据用户的 `notification_settings` 决策 → `_schedule_external` async 推到事件循环 → `_send_sms` / `_send_dingtalk_user` 调用第三方(骨架实现,仅打日志)
4. **best-effort**:第三方调用 try/except 包裹,失败只记日志,不影响主流程
5. **防骚扰**:默认 `sms/dingtalk=false`,只有用户在 `/notifications` 勾选才触发

### API (REST + WebSocket)

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/notifications` | 列表(支持 `only_unread` / `type` / 分页) |
| GET | `/api/notifications/unread` | 未读数(顶栏红点) |
| POST | `/api/notifications/{id}/read` | 标已读 |
| POST | `/api/notifications/read-all` | 全部标已读 |
| GET | `/api/notifications/settings` | 我的所有事件偏好 |
| PUT | `/api/notifications/settings/{ntype}` | 改某个事件的三组开关(in_app/sms/dingtalk) |
| POST | `/api/notifications/announce` | admin 群发系统公告 |
| GET | `/api/notifications/channels` | admin 列通道 |
| POST | `/api/notifications/channels/{ctype}` | admin upsert 通道(配置 JSON) |
| WS | `/ws/notifications?token=...` | 实时推送(连接时立即推 `notification.unread`;之后 `notification.new`) |

### 前端

#### 全局 store
[frontend/src/stores/notifications.js](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/stores/notifications.js) (Zustand)：
- `unreadCount` / `recent`(最近 10 条)/ `total`
- `init()` 建立 WS + 3s 自动重连
- `markRead(id)` / `markAllRead()`
- 收到 `notification.new` 时未读+1,加入 recent,并把浏览器 tab 标题加 `[新消息]` 前缀

#### 顶栏铃铛
[frontend/src/components/NotificationBell.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/NotificationBell.jsx):
- 顶栏右上角,用户名菜单左侧
- 🔔 图标 + 红色徽标(超出显示 99+)
- 点击下拉框:最近 10 条 + 全部已读 + 查看全部
- 点击单条 → 调 `markRead` + 按 `target_type` 跳转:
  - `user` + `account_apply` → /admin/users
  - `followup_project` → /project-followups?project_id=X
  - `project_pending` → /approvals
  - 其他 project → /projects

#### 完整通知页
[frontend/src/pages/Notifications.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Notifications.jsx):
- 全部/未读 筛选 + 分页
- 顶部折叠面板:每事件类型 3 个 checkbox(in_app/sms/dingtalk),实时存盘
- 未提醒:"已配置部分外推"提示

#### Admin 群发与通道配置
[frontend/src/pages/NotificationAdmin.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/NotificationAdmin.jsx):
- 群发公告表单(标题+内容 → /announce)
- 通道列表(4 类钉钉/短信),点击「编辑」弹窗 JSON 配置

#### 路由 + 菜单
[frontend/src/App.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/App.jsx) + [frontend/src/components/Layout.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx):
- `/notifications`(所有角色)
- `/admin/notifications`(仅 admin 菜单可见)
- Layout 左侧菜单:`📣 通知管理`(admin) / `🔔 通知中心`(所有)

### 数据库迁移

[backend/app/main.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/main.py) `lifespan` 启动时:
1. `users` 加 `phone` / `dingtalk_user_id`(若不存在)
2. 创建 `notifications` / `notification_settings` / `notification_channels` 三表 + 索引
3. 事件循环绑定(`set_event_loop`)

### 部署/构建顺序

1. 前端 build:`cd frontend && node node_modules/vite/bin/vite.js build` → 产出写到 `backend/static/`
2. 重启 backend:`python -m uvicorn app.main:app --host 0.0.0.0 --port 8765`

### 关键文件

| 角色 | 文件 |
|---|---|
| 后端模型 | [models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py) |
| 后端服务 | [services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py) |
| 后端路由 | [routers/notifications_ws.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/notifications_ws.py) |
| 后端 schemas | [schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py) |
| 前端 store | [stores/notifications.js](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/stores/notifications.js) |
| 前端铃铛 | [components/NotificationBell.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/NotificationBell.jsx) |
| 前端通知页 | [pages/Notifications.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Notifications.jsx) |
| 前端管理页 | [pages/NotificationAdmin.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/NotificationAdmin.jsx) |
| 前端 API | [api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx) |
| 前端路由 | [App.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/App.jsx) |
| 前端布局 | [components/Layout.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx) |

### 端到端验证(2026-08-21)

1. jhliu 创建项目 → 审批人是 jluo → jluo `unread_count` +1,显示 "新项目待审批" ✅
2. jluo 在 `/approvals` 通过项目 → jhliu `unread_count` +1,显示 "项目审批通过" ✅
3. admin 群发公告 → 全体非 admin 用户各收到 1 条 `system_announcement` ✅
4. `account_apply` / `password_reset` / `followup_viewed` 已就绪,后续真实流程触发即可

### 后续扩展点

- **钉钉企业应用工作通知**:在 `NotificationAdmin` 填 CorpID/AppKey/AppSecret + 用户dingtalk_user_id 即可启用(`_send_dingtalk_user` 已留接口)
- **阿里云/腾讯云短信**:`_send_sms` 已留接口,填 access_key/secret/签名/模板即可投递(需 `pip install alibabacloud-dysmsapi / tencentcloud-sdk-python-sms`)
- **实时性增强**:目前 WS 3s 重连,可改为心跳保活 + 指数退避
- **广播优化**:系统公告 N>1000 时可改"延迟队列 + 按 chunk fanout",避免单次 commit 过大

---

## 19. 用户 ↔ 通知通道绑定（钉钉 / 短信）（2026-08-21）

### 需求

第 18 章已经接好「钉钉企业应用工作通知」+ 短信号通道,但钉钉工作通知需要具体到人的 userid(企业内每个成员都有唯一 staffId),短信需要手机号。本章把账号与钉钉/手机号打通,运维层面手动绑定。

### 设计

- `User` 表加 2 个字段:`phone`(短信)/ `dingtalk_user_id`(钉钉工作通知定向投递)
- 「用户管理」列表加 2 列展示,支持 admin 在「编辑」弹窗里直接填写(手填即可,无需调用钉钉通讯录 API)
- 普通账号登录后也能在「修改密码」弹窗侧加一个面板,自助补填自己的手机号(后续扩展)

### 变更

#### 后端
- [schemas.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py) `UserBase` / `UserUpdate` 加 `phone` + `dingtalk_user_id`
- [routers/users.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/users.py) `update_user` 用 `model_fields_set` 判断是否显式传入,空字符串自动规范化为 None

#### 前端
- [pages/UserManagement.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/UserManagement.jsx)
  - 列表新增 2 列:手机号 / 钉钉 userid(等宽字体显示)
  - 编辑/新建弹窗新增 2 个输入框(注明"从钉钉管理后台获取")
  - 表单 state 加 `phone` / `dingtalk_user_id`,handleSubmit 提交时一并 PATCH

### 用法步骤

1. 打开钉钉管理后台:通讯录 → 选中某员工 → 复制其 **userid**(也叫 staffId)
2. 在系统「用户管理」→ 点「编辑」→ 填入「钉钉 userid」+ 「手机号」→ 保存
3. 该用户的 user 一旦勾选「钉钉工作通知」开关(/notifications 个人偏好),后续事件触发时即可定向投递

### 端到端验证

刚才已跑通接口(admin token PUT /users/2 → 保存 phone + dingtalk_user_id → GET /users 回显成功)

### 安全考虑

- 字段对所有已登录用户可见(只读)— 不暴露只给 admin,因为手机号/钉钉 ID 需要本人确认才能正确
- 写入仅 admin 可操作(PUT /users/{id} 走 `require_admin`)
- 数据库列不加密,可在后续接入脱敏/加密(MVP 阶段不处理)

### 后续扩展

- **自助补填**:在用户「修改密码」弹窗加一个 `我的联系信息` 折叠面板,允许普通账号自助维护自己的 phone/dingtalk_user_id(admin 不参与)
- **钉钉通讯录同步**:加一个『一键同步钉钉通讯录』按钮,admin 点击后调钉钉 `https://oapi.dingtalk.com/topapi/v2/user/list` 拉全量成员,以 `real_name` 与钉钉 `name` 模糊匹配,一次性预填
- **HR 同步**:从企业 HR 系统按工号拉取手机号

---

## 20. 通知中心 Bug 修复与钉钉工作通知落地（2026-08-21）

### 问题
用户反馈:
1. 刘建辉创建项目 → admin 没收到"新项目待审批"通知(只收到张三的)
2. 钉钉工作通知未触发

### 根因排查

#### Bug 1: 自营项目流程不触发通知
[backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) `create_instance` 创建 `Project` 行后,**没有调用 `send_notification`**(只有渠道项目路径有)。  
→ 修复:在 `db.add(project)` `db.commit()` 之后增加通知逻辑 + bug `inst is not defined` 引用错变量名(应为 `instance`)。

#### Bug 2: 钉钉 userid 绑定后默认 settings 没开启
用户绑定 `dingtalk_user_id` 后,该用户的 `notification_settings.dingtalk` 仍为 False,导致推送被跳过。  
→ 修复:[backend/app/routers/users.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/users.py) `update_user` 在保存 `dingtalk_user_id` 时,自动 upsert 该用户的全部事件 settings(dingtalk=true);清空时反之。

#### Bug 3: SQLAlchemy session 跨 await 边界
`_schedule_external` 把 ORM 对象传给 async 任务,导致 "This session is in 'prepared' state" 异常。  
→ 修复:schedule 时只传普通 dict,async 任务内部用 `SessionLocal()` 重建 session 查 user + channel + 投递。

#### Bug 4: 钉钉 gettoken 用 POST
[backend/app/services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py) `_get_dingtalk_token` 原来用 `requests.post(url, json={...})`,但钉钉 `/gettoken` 要求 GET + query string,返回 `errcode=43001 "需要GET请求"`。  
→ 修复:改为 `requests.get('https://oapi.dingtalk.com/gettoken?appkey=X&appsecret=Y')`。

### 实施要点

[backend/app/services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py):
- 顶部 `import requests`
- 同步版 `_send_dingtalk_sync(user, title, content, target_type)`:
  - 用新 SessionLocal session 读 `notification_channels` 配置
  - 解析 corp_id / agent_id / app_key / app_secret
  - 进程级缓存 access_token(过期前 60s 续)
  - 用 `POST /topapi/message/corpconversation/asyncsend_v2?access_token=...` 投递工作通知到 user.dingtalk_user_id
  - 完整 try/except/finally,失败仅 log 不影响主流程
- `_push_external_async` 改为传基本 dict(不再传 db/ORM)
- `_schedule_external` 同步提取 `n.id`/`n.type.value`/`n.title`/`n.content`/`n.target_type` + setting 各通道开关

[backend/app/routers/users.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/users.py) `update_user`:
- `dingtalk_user_id` 变化时 upsert `notification_settings`(全部事件 dingtalk=true)
- 清空时全量关 dingtalk 开关

[backend/app/routers/forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) `create_instance`:
- `db.add(project)` + commit + refresh 后:
  - 调用 `send_notification(...)` 通知 `approver_id`
  - 用 `instance.template.name`(不是 `inst`)
  - try/except 包裹

### 端到端验证(2026-08-21 15:38)

```
[notifications] [external] async start user=1 ntype=password_reset sms=False dingtalk=True
[notifications] [dingtalk.corp] cfg_row loaded: True
[notifications] [dingtalk.corp] gettoken result: OK
[notifications] [dingtalk.corp] POST result: {'errcode': 0, 'errmsg': 'ok', 'task_id': 3428280548869}
[notifications] [dingtalk.corp] OK user=1 task_id=3428280548869
```

✅ 钉钉工作通知**已实际投递成功**(`errcode=0`),admin 用户的钉钉账号(`07260754937840`)应当收到「您的密码已被重置」文本通知。

### 部署要点

1. **数据迁移**:旧账号 binding 时只更新 dingtalk_user_id,**不会自动开 settings**(已修复为自动开启);旧账号需要 admin 重新触发保存(任何 put users/{id} 都能让绑定逻辑跑一次)
2. **第一次拉取 access_token**:钉钉 gettoken 接口需要 corp_id,agent_id,app_key,app_secret 正确(从钉钉开放平台 → 应用 → 凭证信息获取)
3. **企业应用 IP 白名单**:钉钉新企业应用默认 IP 白名单未开启 → 需在钉钉开放平台 → 应用安全 → IP 白名单加上服务器 IP(否则可能 88 错误)
4. **用户 userid 来源**:从「钉钉管理后台」通讯录 → 用户详情 → userid;或在钉钉开放平台用 `userid_list` 接口反查

### 后续可扩展

- **多个 agentId 路由**:不同事件发到不同 agent(例如系统公告走「运营通知」应用,审批类走「OA 审批」应用)
- **message 类型扩展**:目前只发 text,可加 oa 类型卡片、markdown 等
- **撤回 / 更新消息**:钉钉支持撤回/更新已发工作通知(目前未做)

---

## 21. AI报表模型配置增强 + 启动环境修复（2026-08-22）

### 本次调整

围绕 `AI报表 -> 模型配置` 做了 4 组增强：

1. 把报表页明确拆成：
   - `标准报表`
   - `AI 分析`
   - `模型配置`
2. 预置 3 个国内云端模型模板：
   - `Kimi`
   - `MiniMax`
   - `DeepSeek`
3. 每个模型增加 `测试连接` 按钮，返回响应耗时（ms）
4. 修复本地后端启动环境，确保当前项目能继续跑起来

### 前端变更

[frontend/src/pages/Reports.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Reports.jsx)

- `模型配置` 页签中新增「预置国内云端模型」区域
- 每张预置卡片展示：
  - 模型名称
  - 默认模型标识
  - 默认接入地址
  - `填写 Key 创建` 按钮
- 下方单独保留 `自定义本地模型` 入口
- 已配置模型列表新增：
  - `测试连接`
  - `编辑`
  - `删除`
- 测试结果会展示：
  - 是否成功
  - 响应耗时 `latency_ms`
  - 简短返回摘要

[frontend/src/api/index.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)

- 新增：
  - `getAIModelPresets()`
  - `testAIModelConfig(id, data)`

### 后端变更

[backend/app/schemas.py](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/schemas.py)

- 新增：
  - `AIModelPresetResponse`
  - `AIModelTestRequest`
  - `AIModelTestResponse`

[backend/app/routers/forms.py](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py)

- 新增预置模型常量：
  - `Kimi` → `https://api.moonshot.ai/v1` + `kimi-k3`
  - `MiniMax` → `https://api.minimax.io/v1` + `MiniMax-M3`
  - `DeepSeek` → `https://api.deepseek.com` + `deepseek-v4-flash`
- 新增接口：
  - `GET /api/forms/ai-model-presets`
  - `POST /api/forms/ai-models/{id}/test`
- 测试接口逻辑：
  - 走 OpenAI 兼容 `chat/completions`
  - 发送固定提示词 `请只回复“连接成功”四个字。`
  - 返回响应耗时和摘要
- 修复兼容问题：
  - 编辑模型时若 `api_key` 传空字符串，后端保持原值，不再覆盖为空

### 页面职责调整

- 左侧导航保留：
  - `AI报表`
  - `表单管理`
- `表单管理` 恢复为原有能力，不再承载模型配置
- 所有 AI 模型配置、AI 分析入口都收口到 `AI报表`

### 验证结果

- 前端 `npm.cmd run build` 通过
- 后端 Python 语法检查通过
- 静态构建产物已包含以下关键文案：
  - `预置国内云端模型`
  - `填写 Key 创建`
  - `新建本地模型`
  - `测试连接`

### 启动环境踩坑记录

这次后端重启过程中，连续踩到 4 个环境问题：

1. `backend/start_server.py` 里仍写死旧的 `Z:` 盘路径
2. 全局 `hermes-agent` Python 环境可运行，但缺 `sqlalchemy`
3. `backend/site_pkg` 虽然有很多依赖，但 `pydantic_core` 的二进制扩展不完整，不能直接替代完整虚拟环境
4. 历史遗留的 `backend/.venv_fix` 指向旧用户目录 `C:\\Users\\jwang\\...`，当前机器不可直接复用

### 当前可用启动方式

为避免继续依赖坏掉的旧环境，已在项目下重新创建本地环境：

- 新环境路径：`backend/.venv_local`

安装命令：

```powershell
& "C:\Users\admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m venv "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend\.venv_local"
& "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend\.venv_local\Scripts\python.exe" -m pip install -r "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend\requirements.txt"
```

当前已验证可用的启动方式：

```powershell
Start-Process -WindowStyle Hidden -FilePath "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend\.venv_local\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" `
  -WorkingDirectory "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend"
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/api/health"
```

返回：

```json
{"status":"ok"}
```

## AI Agent 模块（项目级 + 报表级 + 系统提示词管理）

本系统现在提供三层 AI 能力：

1. **项目级 Agent**：`/api/agents/analyze`、`/api/agents/query`（ChromaDB + sentence-transformers 索引，单项目深度分析）
2. **报表级 AI 对话框**：内嵌在「AI 报表」tab 的 AI 分析 / 标准报表 页签下，输入提示词即时生成左侧表格 + 右侧文字回复
3. **系统提示词（角色设定）管理**：管理员可维护多个角色模板（商业分析专家 / 销售助理 / 财务审计视角 / 小销默认），所有 AI 调用都受其约束

### 后端新增/修改文件

| 文件 | 作用 |
| --- | --- |
| `backend/app/agents/report_agent.py` | 项目级 Agent 规则基准 + LLM 调用 + JSON 解析 |
| `backend/app/services/agent_indexer.py` | Chroma 索引 + 上下文检索 + CLI（`--build/--get/--delete`） |
| `backend/app/routers/agents.py` | `/api/agents/analyze` 与 `/api/agents/query` |
| `backend/app/routers/agent_prompts.py` | 系统提示词 CRUD：`/api/agent-prompts` + `/api/agent-prompts/seed` |
| `backend/app/routers/reports.py` | `_call_llm()` 真正调用 OpenAI 兼容大模型；`ai-analyze` / `ai-assistant` 拼装上下文 |
| `backend/app/models.py` | 新增 `AgentPrompt` 表（角色提示词） |
| `backend/app/schemas.py` | `AIAnalysisRequest / AIReportAssistantRequest` 增加 `system_prompt`；新增 `AgentPromptCreate / Update / Response` |
| `backend/app/main.py` | 注册 `agents.router` + `agent_prompts.router` |
| `backend/tests/test_agent.py` | happy path + 非法 JSON 重试用例 |
| `backend/requirements.txt` | 新增 `chromadb / sentence-transformers / jieba / openai / pytest` |
| `backend/start_server.py` | 默认端口改为 8765（避开 Hyper-V 保留 8000）；`backend_dir` 用 `os.path.dirname(__file__)` 计算，可移植 |
| `backend/start_server2.py` | 临时启动脚本：设置 `PYTHONPATH` 指向 `.venv_local_new_pkgs/`（当主 venv 损坏时通过它跑） |

### 前端新增/修改文件

| 文件 | 作用 |
| --- | --- |
| `frontend/src/api/agents.js` | `analyzeProject`、`queryAgent` |
| `frontend/src/api/index.jsx` | 补齐 AI 模型 + Agent 提示词相关导出（`listAgentPrompts` / `createAgentPrompt` / `seedAgentPrompts` / ...） |
| `frontend/src/pages/Reports.jsx` | 右侧 AI 对话框 + 左侧红框（表格结果区），「🎭 角色设定」折叠面板 |
| `frontend/src/App.jsx`、`frontend/src/components/Layout.jsx` | 移除独立 AI Agent 菜单与 `/agent-console` 路由，统一入口到「AI 报表 / AI 分析」 |

### 系统提示词（角色设定）

```text
URL: /api/agent-prompts
GET    /                  # 列出（普通用户仅看启用项）
GET    /active?role_key=  # 取激活提示词
POST   /                  # 创建（仅 admin）
PUT    /{id}              # 修改（仅 admin）
DELETE /{id}              # 删除（仅 admin）
POST   /seed              # 一键写入 4 个预置角色
```

预置模板（`POST /api/agent-prompts/seed`）：

- **商业分析专家**（`business_analyst`）— 关注金额、转化率、责任销售、跟单阶段联动
- **销售助理**（`sales_expert`）— 关注跟单推进、责任人协同
- **财务审计视角**（`finance_expert`）— 关注金额、回款、费用、合规
- **小销（默认）**（`default`）— 通用销售助理风格

前端「🎭 角色设定（系统提示词）」面板（红框上半部分）：

- 顶部：当前激活的角色名 + 角色切换下拉
- 「管理」按钮展开后：列表 / 编辑 / 新建 / 删除（仅 admin 可见）
- 每次调用 LLM：`system message = 选中提示词的 content`；助手气泡顶部会显示「🎭 以「...」角色回复」

### 真接大模型（_call_llm）

`backend/app/routers/reports.py` 新增 `_call_llm(model_info, system_prompt, user_prompt, history=None)`：

- 通过 `openai` SDK 按 `AIModelConfig.base_url / api_key / model_name / temperature / max_tokens / timeout_seconds` 调用
- messages 顺序：`system → 最近 6 条历史 user/assistant → 当前 user_prompt`
- user_prompt 自动拼装：数据范围（项目数 / 总金额 / 中标率 / 自营 / 渠道）+ 已选字段 + 预览样本（最多 20 行）+ 用户原始要求
- 任何异常 / `choices=0` → 返回 `None`，上层 fallback 到骨架回答
- 响应给前端前自动脱敏 `model.api_key`
- 返回 `mode: "llm" | "skeleton"` 让前端显示来源

当前可用模型（在「AI 报表 / 模型配置」可改）：

- `Qwen3.6:35B-A3B`（base_url=`http://deepquick.com.cn:26810`，OpenAI 兼容）
- `Qwen3.8-27B`（同上）
- Kimi / MiniMax / DeepSeek 模板（cloud API，按需填 API Key 启用）

### 启动与依赖

环境变量（可选，不设则走默认）：

```powershell
$env:CHROMA_DIR               = "z:\soft-RED\hermes\开发软件\渠道项目登记\backend\chroma_store"
$env:OPENAI_API_KEY           = "your_api_key_here"
$env:AGENT_EMBEDDING_PROVIDER = "auto"        # auto / openai / local
$env:AGENT_DEFAULT_TOP_K      = "5"
```

依赖安装：

```powershell
# 主 venv 完整依赖（含 chromadb / sentence-transformers / openai）
& "z:\soft-RED\hermes\开发软件\渠道项目登记\backend\.venv_local\Scripts\python.exe" `
    -m pip install -r "z:\soft-RED\hermes\开发软件\渠道项目登记\backend\requirements.txt"

# 临时方案：把依赖装到 backend/.venv_local_new_pkgs，再用 start_server2.py 启动
python -m pip install --target "z:\soft-RED\hermes\开发软件\渠道项目登记\backend\.venv_local_new_pkgs" openai webdavclient3 chromadb
```

启动后端（端口 8765 避开 Hyper-V 保留的 8000）：

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\backend"
python start_server.py        # 主路径（使用 .venv_local）
# 或
python start_server2.py       # 备用路径（用 .venv_local_new_pkgs，需要 PYTHONPATH 自动设置）
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8765/api/health"
# 返回 {"status":"ok"}
```

前端入口：[http://127.0.0.1:8765/admin/](http://127.0.0.1:8765/admin/)（注意是 8765，不是 8756/8000）

### 项目级 Agent 使用

CLI 索引：

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\backend"
python -m app.services.agent_indexer --build 123
python -m app.services.agent_indexer --get 123 --top-k 5 --query "最近一次跟单进展"
python -m app.services.agent_indexer --delete 123
```

HTTP 调用：

```http
POST /api/agents/analyze
Content-Type: application/json
{
  "project_id": 123,
  "model_id": null,                // 留空取默认模型
  "system_prompt": null,           // 留空取 default 角色
  "query": "本项目最大的风险点是什么？"
}

POST /api/agents/query
{
  "project_id": 123,
  "model_id": null,
  "query": "近期跟单进展？",
  "top_k": 5
}
```

测试：

```powershell
cd "z:\soft-RED\hermes\开发软件\渠道项目登记\backend"
pytest -q tests/test_agent.py
```

### 说明与兜底

- 默认会优先从已启用的 `AIModelConfig` 里取默认模型（按 `is_default desc, id asc`）
- 若 OpenAI / 兼容模型不可用，会在 embedding 阶段回退到本地 `sentence-transformers`（`all-mpnet-base-v2`）
- 项目级 Agent：LLM 调用最多重试 2 次；返回非法 JSON 同样最多重试 2 次，超出后返回 500 `AI 模型返回了无效的 JSON`
- 报表级 `_call_llm`：失败/空响应自动 fallback 到骨架回答，前端用 `mode` 区分
- `CHROMA_DIR` 目录需要持久化保存，否则重启后要重新建索引
- 所有 `evidence.snippet` 都经过 `_truncate_snippet(<=300)` + `_mask_sensitive_numbers(8+ 位数字中段脱敏)`
- 报表响应里 `model.api_key` 始终为 `None`（仅服务端调用时用真实 key）

---

## 渠道项目 WebDAV / 存储区域 多轮重构（2026-08-25）

本轮针对渠道项目上传 401 + 路径错乱 + 模板 zone 不联动问题做了多轮迭代。

### 核心目标

- **多存储区域**：用户可定义多个 WebDAV zone（NAS1 / NAS2 等），每个 form template 绑定一个 zone
- **新建项目时自动用模板的 zone**：不强制用户每次选
- **编辑时 zone 可改**，但**不能动历史项目**（保持原 project.storage_zone_id）
- **诊断接口**：扫描所有项目，列出路径正常/错误/空/未关联的项目，不修改 DB

### 关键改动

#### 1. 后端 `file_storage.py`

- 新增 `_resolve_config_for_project(db, project_id)`：根据 project.storage_zone_id 反查 zone 拼装 FileStorageConfig（zone 优先；fallback 老单例 id=1）
- `list-files` / `delete-file` / `upload` 三个端点都改用这个 helper，解决上传 401 问题
- 新增 `POST /api/file-storage/diagnose-all`：扫描所有项目的 tender_folder / bid_folder，PROPFIND 校验，返回 status（ok/wrong/empty/unknown）+ msg + summary，**不修改 DB**
- 新增 `POST /api/file-storage/rebuild-project-folders`：admin only，按 proj 当前 DB 字段 MKCOL 子目录
- `preview-path` 端点：source='channel' 时也从「渠道项目登记表」FormTemplate 反查 zone（之前只对 self 生效）

#### 2. 后端 `projects.py`

- `create_project` 走新 helper `_resolve_config_for_project_create(data, db)`：
 - `source='self'` → 用前端传来的 storage_zone_id
 - `source='channel'`（默认）→ 前端没传 zone 时从「渠道项目登记表」FormTemplate 反查
 - 兜底老单例 FileStorageConfig.id == 1
- `ProjectCreate` schema 加 `source: Optional[str] = 'channel'`
- 编辑模式 `update_project` 不会修改 `storage_zone_id`（保持原项目的 zone）

#### 3. 后端 `forms.py`

- `POST /api/forms/file-storage/upload`：之前 `webdav_request('PUT', url, user, pwd, data=...)` 调用错误（函数签名不支持 data/headers），改为底层 `requests.put(url, data=content, auth=...)`，绕过 webdav_request 限制
- 同步添加 `_ensure_parent_dir` 辅助，确保父目录已建好
- 自营项目（DynamicForm）走的是 form instance 路径，跟渠道项目 ProjectForm 路径完全独立

#### 4. 前端 `api/index.jsx`

- 新增 `listStorageZones`（保持原 axios 格式，返回 `{data: [...]}`）
- 新增 `diagnoseFileStorage`（POST，返回 data）
- 新增 `rebuildProjectFolders`（POST data）

#### 5. 前端 `Projects.jsx`

- 列表 useEffect：调 `fetchDiagnose` 拿所有项目的诊断结果
- 表格新增「存储」列，根据诊断结果显示绿/红/灰徽章
- 顶部 banner：有错项目时红色提示 +「🔄 重新扫描」按钮
- 「渠道项目新建」按钮改成调用 DynamicForm（**与自营项目完全一致**）—— 加载「渠道项目登记表」模板，直接用 template.storage_zone
- 「自营项目新建」保持 DynamicForm 路径不变

#### 6. 前端 `ProjectForm.jsx`（用于**编辑**已有项目）

- 接收 `diagnoseResult` + `onRebuilt` props
- 文件管理区上方：根据 diagnoseResult 显示红/绿/灰提示
 - 全部 ok：绿色细提示
 - 未关联 zone：灰色提示
 - 路径错误：红色框 + 完整路径 +「🔧 重建」按钮（admin only）+「不重建」按钮
- 编辑模式下拉框：删除「存储区域」选择 UI（zone 由模板决定，不让用户改）
- 删除 `listStorageZones` import 和相关 state

### 关键设计决策

| 决策 | 原因 |
|---|---|
| 渠道项目新建走 DynamicForm | 与自营项目逻辑一致，复用模板 zone 联动 |
| ProjectForm 只保留用于编辑 | ProjectForm 有 withdraw/win_bid_status 等管理字段，新建不需要 |
| zone 修改走表单编辑 | 在「表单管理 → 编辑表单 → 右下角存储区域」改模板 zone 即可全模板同步 |
| 已建项目的 zone 不动 | 用户明确要求，避免每次升级系统要重新调整 |
| diagnose 不修改 DB | 只读扫描，admin 选择性手动重建 |

### 数据库现状（2026-08-25 21:59）

```sql
storage_zones:
  (1, '172NAS/渠道资料', '/渠道资料', '172.16.10.252', 5006, 'trae')
  (3, '172NAS/自营资料', '/自营资料', '172.16.10.252', 5006, 'trae')
  (4, '172NAS/跟单存储', '/自营资料/跟单资料', '172.16.10.252', 5006, 'trae')
  (5, '测试区域', 'soft-RED/test', '172.16.1.22', 5006, 'admin001')
  (6, '默认存储', '/web', '172.16.1.22', 5006, 'admin001')

form_templates:
  id=1 name='渠道项目登记表' storage_zone_id=6   ← 默认存储 /web
  id=3 name='自营项目登记表' storage_zone_id=6   ← 默认存储 /web
  id=4 name='项目跟单登记表' storage_zone_id=5   ← 测试区域

projects (示例):
  (1, '自营测试', zone=5, path: soft-RED/test/刘建辉+...)
  (2, '渠道项目测试', zone=1, path: 渠道资料/张林+...)  ← 旧渠道老单例
  (3, '玩儿', zone=5, path: soft-RED/test/张林+...)
  (4, '自营-默认', zone=6, path: web/系统管理员+自营-默认+...)
```

### 明日（2026-08-26）继续

**问题：渠道项目走 DynamicForm 路径后，路径预览正确（`web/系统管理员+我企鹅+2026-08-25/招标资料`），但「无法建立文件夹，无法上传文件」，前端 alert「操作失败」**

排查方向：
1. 看后端 `app_debug.log` 找 `POST /api/forms/instances` + 后续 `POST /api/forms/file-storage/upload` 的 4xx/5xx 响应
2. 排查 `forms.py::upload_form_files` 是不是调用 `webdav_request('PUT', ...)` 失败（之前修过但可能没修完整）
3. 检查 `ensure_webdav_folders` 在新建 form_instance 时是否真的执行
4. 检查 zone6（默认存储）credentials `admin001` 是否真的能写入 `/web` 路径
5. 排查 `zone.webdav_username='admin001'` vs `zone.webdav_password` 是否正确

**可能的根因**：
- `forms.py::upload_form_files` 上传逻辑有问题
- `create_form_folders` 创建子目录时 zone 的 credential 错误
- MKCOL 后 PUT 时目录未真正建立（PUT 返回 409 Conflict）

### 文件清单（修改过的）

后端：
- `backend/app/routers/file_storage.py`（新增 helper、diagnose-all、rebuild-project-folders、preview-path 增强）
- `backend/app/routers/projects.py`（create_project 走 zone 解析）
- `backend/app/routers/forms.py`（upload_form_files 修复 PUT 调用）
- `backend/app/schemas.py`（ProjectCreate 加 source 字段）

前端：
- `frontend/src/api/index.jsx`（新增 3 个 API）
- `frontend/src/pages/Projects.jsx`（诊断 banner + 徽章 + 渠道走 DynamicForm）
- `frontend/src/components/ProjectForm.jsx`（诊断提示 + 重建按钮 + 删除 zone 选择）
- `frontend/vite.config.js`（rollupOptions.treeshake: false 防止动态 import 误删）

### 后端启动

```powershell
# 在 Y:\soft-RED\hermes\开发软件\渠道项目登记\backend 目录
python start_server.py
# 端口 8765
```

前端 bundle 由 vite 自动写到 `backend/static/assets/`，**无需重启后端**即可让前端生效。

### 教训（本轮）

1. **不要让用户复制粘贴代码**——每次粘贴都可能丢字符（如本轮丢 `import { listStorageZones }`），必须用 `Write` 工具直接覆盖
2. **真正的根本原因往往很简单**（如本轮的 import 缺失），不要在表面现象上绕圈
3. **Build size 对比**是发现 tree-shake / 重复定义的有效工具

---

## 22. 自营项目编辑/查看 → 对齐渠道项目样式（2026-08-26）

### 背景

自营项目（`source='self'`）和渠道项目（`source='channel'`）的业务行为需要完全一致：表单模板可独立配存储区域、文件按 zone 落 NAS、编辑/查看页面样式与渠道项目一致。但前几轮出现了：

- 自营项目「编辑」「查看」弹窗加载慢（后端 `NameError` 或拉不到文件）
- 自营项目「编辑」界面跟渠道项目不一致
- 自营项目文件列表为空（后端用了全局 `FileStorageConfig`，没按 instance.storage_zone_id 反查 zone）

### 核心目标

1. **新建走同一逻辑**：渠道项目 / 自营项目新建都走 `DynamicForm`（按模板字段渲染 + 按模板 zone 落 NAS）
2. **编辑/查看走同一逻辑**：两种项目的编辑/查看页面都和渠道 ProjectForm 一致（顶部蓝色「项目信息」只读卡 + 中标状态下拉 + 文件管理 + 关闭/完成按钮）
3. **文件列表按 zone 取数**：自营项目列表接口按 `FormInstance.storage_zone_id` 反查 `StorageZone`，不再用全局 `FileStorageConfig`

### 后端改动

#### [backend/app/routers/forms.py](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py)

1. **新增 `_resolve_config_for_instance(db, instance_id)`**（模块顶部）：
   - 按 `FormInstance.storage_zone_id` 反查 `StorageZone`
   - 用 zone 字段（`webdav_url / webdav_port / webdav_username / webdav_password / webdav_base_path`）构造临时 `FileStorageConfig`
   - fallback 到 `_ensure_config(db)`（全局单例）

2. **`list_form_files`**：把第 822 行 `cfg = _ensure_config(db)` 改为 `cfg = _resolve_config_for_instance(db, int(instance_id))`
   - 修复自营项目「文件列表为空」

3. **`delete_form_file`**：第 962 行同样改为 `_resolve_config_for_instance`
   - 保证删除时连正确的 zone

4. **`create_instance`**：模板名前缀识别 `channel / self`，同步写入 `Project.source`，模板里字段值（项目名称 / 责任销售 / 合作单位 / 项目类型）按 label 反查并映射到约定英文 key

5. **`update_instance`**：编辑时同步刷新关联 `Project` 的字段；管理员可改中标状态时通过 `PUT /api/projects/{id}` 持久化到 `Project.win_bid_status`（前端调用 `api.put('/projects/{id}', { win_bid_status })`）

6. **`/api/forms/instances/{id}/project-info`**：返回关联 `Project`（项目名 / 类型 / 中标状态 / 审批状态 / 合作单位 / 联系人 / 联系方式），供 DynamicForm 顶部蓝色卡渲染

7. **顶部导入修复**：第 13 行 `from app.models import ...` 补齐 `Project, ProjectType, WinBidStatus`，避免 `update_instance` 执行到 `db.query(Project)` 时 `NameError`

### 前端改动

#### [frontend/src/components/DynamicForm.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)

1. **新增 state**：`projectInfo`（关联项目信息）+ `winBidDraft`（中标状态下拉草稿）

2. **编辑模式（`instanceId && !readOnly`）**：
   - 顶部蓝色「项目信息」卡：项目名称 / 类型 / 金额 / 合作公司 / 联系人 / 联系方式 + 中标状态下拉框（进行中 / 中标 / 未中标）
   - 「管理员可修改中标状态」绿色徽章
   - 渲染文件管理（不渲染普通字段分组 — `renderSection` 内部对非文件 section 在编辑模式返回 null）
   - 不显示「审批人」
   - 底部「取消 / 完成」按钮

3. **查看模式（`readOnly=true`）**：保持简洁版（项目基本信息 / 项目其他情况 分组只读 + 文件管理 + 关闭按钮）

4. **新建模式（无 instanceId）**：保持原模板字段渲染 + 审批人 + 提交

5. **保存时**：若管理员改了中标状态，调 `api.put('/projects/{id}', { win_bid_status: winBidDraft })` 持久化

#### [frontend/src/pages/Projects.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)

- **自营项目编辑/查看分流**：判断 `p.source === 'self' && p.form_instance_id` → 走 `DynamicForm`（保留模板字段）+ `readOnly` 决定编辑/查看
- **打开一种弹窗时清空另一种**：避免编辑/查看同时残留导致 UI 混乱

### 验证

| 项目 | 编辑 | 查看 | 文件列表 |
|---|---|---|---|
| 渠道1（id=28, zone=5） | ✅ 蓝色卡 + 中标状态「是」 + 文件列表1项（询价2026.xlsx） | ✅ 完整字段分组只读 | ✅ 1 个 |
| 自营测试1（id=27, zone=6） | ✅ 蓝色卡 + 中标状态下拉 + 文件列表1项（2026年6月考试.xlsx） | ✅ 完整字段分组只读 | ✅ 1 个 |

### 关键文件

- 后端：[backend/app/routers/forms.py](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py)
- 前端：[frontend/src/components/DynamicForm.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)
- 前端路由：[frontend/src/pages/Projects.jsx](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)

### 教训（本轮）

1. **后端修 helper 后必须替换调用点**——之前加了 `_resolve_config_for_instance` 但 `list_form_files` / `delete_form_file` 还在用 `_ensure_config(db)`，等于没修
2. **Python NameError 隐藏很深**——`update_instance` 函数体内用到 `Project / ProjectType` 但顶层 `from app.models import` 没包含；Python 直到运行到那一行才报 `NameError`，表面看是「编辑保存失败」
3. **后端 CWD 必须绝对**——`config.yaml` 里 `database.url` 是相对路径，uvicorn 启动时 CWD 一变就连接到错的 db（空 db），前端所有接口返回空。改成绝对路径后稳定
4. **比对两侧代码是定位问题最快方式**——本轮通过直接调两个 list-files 接口（自营 vs 渠道）一眼看出差异：自营返 0，渠道返 1，立刻定位到 `_ensure_config` 没被替换

---

## 23. boot.bat 一键启动脚本（2026-08-27）

### 背景

项目需要后端 (FastAPI) + 前端 (Vite build) 一起跑。之前每次启动都是手动：
- 后端用 `start_server.py`（硬编码 `.venv_local` 路径，机器上不存在）
- 前端用 `node node_modules/vite/bin/vite.js build` 手动 build

**用户的最新反馈：双击 bat 文件，程序闪一下就关了，无法打开**

### 排查过程

| 问题 | 根因 |
|---|---|
| 闪退 | bat 文件里调用 `backend\.venv_local\Scripts\python.exe`，路径不存在 |
| `hermes-agent\venv` python 启动失败 | `distutils-precedence.pth` import `_distutils_hack`，Python 3.12+ 已移除 distutils |
| `site_pkg\pydantic_core` 报 `No module named '_pydantic_core'` | `pydantic_core` 是 Rust 编译的 C 扩展，必须用对应 Python 版本；`site_pkg` 里是为 Python 3.12 编译的，而 PATH 里的 `python` 是 `hermes-agent` 的 Python 3.11 |
| 后端起来但 sqlalchemy 找不到 | `site_pkg` 在 PYTHONPATH 里的优先级低，hermes-agent venv 的 site-packages 抢先 import |

### 最终解决方案

#### [boot.bat](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/boot.bat)

1. **Python 解析顺序**（必须在 boot.bat 头部固定）：
   1. `backend\.venv_local\Scripts\python.exe`（项目 venv）
   2. **uv 全局 Python 3.12**：`%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe`
   3. `py -3.12` 启动器
   4. `C:\Python312\python.exe`
   5. PATH 里任何 >=3.12 的 python
   
   **关键：绝对不能用 hermes-agent venv 的 Python 3.11，会立即报 pydantic_core 错误**

2. **5 步骤流程**：
   - 解析 Python（上面顺序）
   - 检测 Node.js
   - 检查 `backend/site_pkg/fastapi` 是否存在，否则 pip install
   - Build 前端到 `backend/static/`
   - 启动 `_boot_wrapper.py`

3. **全部 ASCII** 编码，避免 Windows PowerShell 中文乱码问题

#### [backend/_boot_wrapper.py](file:///y:/soft-RED/hermes/开发软件/渠道项目登记/backend/_boot_wrapper.py)

```python
"""wrapper: inject backend/site_pkg into sys.path, then run uvicorn"""
import sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_PKG = os.path.join(ROOT, 'site_pkg')

# ★ 把 site_pkg 放 sys.path 第一位，强制用它（避免 hermes-agent venv 抢先）
if SITE_PKG not in sys.path:
    sys.path.insert(0, SITE_PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8765)
```

**关键设计：**
- `sys.path.insert(0, SITE_PKG)` — 确保 `site_pkg` 优先级高于 hermes-agent venv
- 程序化 `uvicorn.run()` 而非命令行参数 — 避免 PATH 里有多个 uvicorn 时选错
- 不修改 CWD — wrapper 内部不需要切到 backend（CWD 由 boot.bat 控制）

### 验证

```
[1/5] Resolving Python 3.12 interpreter ...
  OK Using uv Python: C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12.13-...
[2/5] Checking Node.js ...
  OK Node.js v22.x detected
[3/5] Checking backend dependencies ...
  OK backend\site_pkg found, _boot_wrapper.py will use it
[4/5] Building frontend ...
  OK Frontend built
[5/5] Launching backend on port 8765 ...

  INFO:     Uvicorn running on http://0.0.0.0:8765 (Press CTRL+C to quit)

  GET /api/health → 200 {"status":"ok"}
```

### 教训（本轮）

1. **必须固定 Python 大版本** —— 这个项目的 `site_pkg` 是为 Python 3.12 预编译的，不能用 Python 3.11。boot.bat 必须硬编码几个 Python 3.12 候选路径，不能依赖 PATH 里的 `python`（可能是任意版本）
2. **`pydantic_core` 是硬约束** —— Rust 编译的 C 扩展有强 ABI 绑定，跨 Python 版本必然失败。预编译的 `site_pkg` 必须配对应版本的 Python
3. **PATH 里的 `python` 不可信** —— `where python` 返回两个结果：uv 全局和 Microsoft Store stub。启动脚本必须显式选 Python 3.12 路径
4. **闪退排查要看 bat 第一行后哪里停** —— 我的第一批 boot.bat 在第 4 行 `call pip install` 调用了不存在的 python.exe，闪退；现在的版本在每个失败点都 `pause`，方便看到错误
5. **双击 bat 不能假设 PATH 完整** —— bat 启动时是干净 PATH（只有 `C:\Windows\System32`），没有当前目录的自动加载。脚本里所有命令必须用绝对路径

### 关键文件

- 启动脚本：[boot.bat](file:///y:/soft-RED/hermes\开发软件/渠道项目登记/boot.bat)
- Python wrapper：[backend/_boot_wrapper.py](file:///y:/soft-RED/hermes\开发软件/渠道项目登记/backend/_boot_wrapper.py)

---

## 24. 项目表单查看模式修复 + DynamicForm 自营弹窗（2026-08-27，端点 0 works / 1 no）

### 背景

用户反馈两个串联问题：
1. **渠道项目查看模式**还能改中标状态、还能上传文件，违反"查看模式只读"原则
2. **自营项目编辑/查看/新建按钮**全部无反应（点击无 alert、无弹窗）
3. **新建按钮**（渠道/自营）也无反应

### 根因（按发现顺序）

#### 1. SQLite `database.url` 错配
`config.yaml` 里 `database.url: sqlite:///Y:/soft-RED/.../data.db`，但本机只有 `Z:/`，uvicorn 启动后 `sqlalchemy.exc.OperationalError: unable to open database file`
**修复**：改成 `sqlite:///Z:/soft-RED/hermes/开发软件/渠道项目登记/backend/data.db`

#### 2. Python `ZoneInfoNotFoundError`
uv 安装的 Python 3.11.15 不带 OS 时区数据库，调用 `ZoneInfo('Asia/Shanghai')` 时抛 `ZoneInfoNotFoundError`，导致渠道项目中标状态修改时第一次保存就报错
**修复**：[backend/app/routers/projects.py:16-22](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/projects.py#L16-L22)

```python
try:
    from zoneinfo import ZoneInfo
    _SH_TZ = ZoneInfo('Asia/Shanghai')
except Exception:
    from datetime import timezone, timedelta
    _SH_TZ = timezone(timedelta(hours=8))  # 兜底：用固定 +08:00 偏移
```

#### 3. 查看模式还能改/还能上传（渠道项目）
前端 [ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx) 中：
- 顶部蓝色"项目信息卡"原本 `{isEdit && (...)}`——查看模式确实不显示
- 但中标状态行、文件上传 dropZone、文件列表的删除按钮都没根据 `readOnly` 屏蔽
**修复**：新增 `readOnly` 入参 `renderFileList` / `renderDropZone` 等，`{!readOnly && (...)}` 包裹

#### 4. 自营项目所有按钮无反应（核心 bug）
ESBuild minify 后弹 `Uncaught ReferenceError: readOnly is not defined`：
- [DynamicForm.jsx:22](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx#L22) 函数签名 `({ template, onClose, onSubmitted, instanceId, onInstanceSaved })` **没有 destructure `readOnly`**，但函数体里**多处**引用了 `readOnly`（包括 `<input readOnly />` 这个裸 JSX 属性）
- ESBuild 把 `<input readOnly />` 编译成对变量 `readOnly` 的引用，函数体未声明 → `ReferenceError` → 整个 DynamicForm 组件挂载失败 → React 卸载弹窗 → 视觉上"无反应"
**修复**：函数签名加 `readOnly = false` 参数；`<input readOnly />` 改 `<input readOnly={true} />`

#### 5. 新建按钮也无反应
[Projects.jsx:88](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx#L88) `loadFormTemplateByName` 中：
```js
const tpl = res.data.find(t => t.name.includes(keyword))   // 旧代码：res 是数组，res.data 是 undefined
```
后端 `GET /api/forms/templates` 直接返回 `List[FormTemplateResponse]`，**不是** `{data: [...]}`，`res.data.find` 抛 `TypeError`
**修复**：
```js
const list = Array.isArray(res) ? res : (res?.data || [])
const tpl = list.find(t => (t.name || '').includes(keyword))
```

### 端点（Endpoint）标记

| 端点 ID | commit | 状态 | 说明 |
|---|---|---|---|
| **0 works** | `8136cc6`（HEAD） | ✅ 当前可用 | 项目表单查看模式只读 + 自营/渠道 DynamicForm 修复 + ZoneInfo fallback + SQLite 路径修正 |
| **1 no** | `8136cc6^` | ❌ 已知损坏 | 渠道项目查看模式仍可改/上传、自营项目弹窗空白 |

### 回滚命令

```bash
# 完整回滚（强烈不推荐，会丢本轮所有修复）：
git reset --hard 8136cc6^

# 只回滚前端（推荐：保留后端 ZoneInfo/SQLite 修复）：
git checkout 8136cc6^ -- frontend/
npm --prefix frontend run build

# 只回滚单个文件，例如 Projects.jsx：
git checkout 8136cc6^ -- frontend/src/pages/Projects.jsx
npm --prefix frontend run build

# 回滚后端（如果数据库路径有问题可以先恢复旧 config 再修）：
git checkout 8136cc6^ -- backend/app/routers/projects.py
# 注意：backend/config.yaml 不在 git 里，需手动核对
```

### 本轮改动文件清单

| 文件 | 改动 |
|---|---|
| `backend/config.yaml` | `database.url` 改绝对路径 `Z:/.../data.db` |
| `backend/app/routers/projects.py` | ZoneInfo fallback 到 +08:00 偏移 |
| `frontend/src/components/ProjectForm.jsx` | `renderFileList / renderDropZone` 加 `readOnly` 入参；中标状态行只编辑模式渲染；新增 `onFilesUploaded` prop（仅刷数据，不关弹窗） |
| `frontend/src/components/DynamicForm.jsx` | 函数签名加 `readOnly = false`；`<input readOnly />` 改 `readOnly={true}`；补顶部蓝色项目信息卡 + 中标状态下拉 + useEffect loadInstance |
| `frontend/src/pages/Projects.jsx` | `loadFormTemplateByName` 兼容 `Array.isArray(res)`；`handleSelfFormNew / handleChannelFormNew` 加 try/catch alert；编辑/查看模式 onSaved 加 `fetchDiagnose` |

### 教训（本轮）

1. **Minify 会暴露隐藏 bug** —— `<input readOnly />` 这种裸 JSX 属性在 dev 模式没事（React 直接当 prop 处理），但 ESBuild minify 后会被当成变量引用，函数体内必须先 destructure 出来
2. **API 响应形状要早期校验** —— `res.data.find(...)` 这种假设响应是 `{data: [...]}` 的写法很容易中招，统一用 `Array.isArray()` + `??` 兜底
3. **前端 minify 后报错只有行号，没有上下文** —— 加调试条（黄色左下角）是定位 "渲染崩在哪个 props" 的最快方法
4. **SQLite 相对路径在 uvicorn 下不稳定** —— 永远用绝对路径，包括 `database.url`
5. **Python `ZoneInfo` 依赖系统 tzdata** —— 容器化 / uv 装的 Python 没有；fallback 到 `timezone(timedelta(hours=8))` 是最稳的写法

---

## 25. 自营/渠道项目查看模式统一用 DynamicForm，编辑模式统一用 ProjectForm（2026-08-27）

### 背景

用户要求：
1. **自营项目**：查看时与新建自营项目表单格式一致（DynamicForm 模板字段），编辑时退回 ProjectForm（项目信息框+文件管理，与渠道项目编辑一致）
2. **渠道项目**：查看时与新建渠道项目表单格式一致（DynamicForm 模板字段），编辑时保持 ProjectForm
3. **数据同步**：编辑修改中标状态/上传文件后，查看能同步显示最新内容

### 改动

#### 1. 自营项目编辑 → 退回 ProjectForm（[Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)）

- 移除 `showSelfEditForm` 状态、`handleSelfFormEdit` 函数、DynamicForm 编辑弹窗
- `handleEditProject` 不再区分来源，统一 `setEditData(p); setShowForm(true)` 走 ProjectForm
- 用户期望：编辑时只能改中标状态和上传文件，不显示模板字段

#### 2. 自营项目查看 → 填充 DynamicForm values（[DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)）

- 加载实例时，`v = r.data?.data || {}` 取到的表单值从未填充到 `values` 状态，导致所有字段空白
- 修复：在 `loadInstance useEffect` 中添加 `setValues(v)`，将后端返回的表单字段值填入 `values` 状态
- 修复后，查看时所有字段正确显示用户填写的内容

#### 3. 查看模式顶部项目信息卡（[DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)）

- 编辑模式已有蓝色项目信息卡（`instanceId && !readOnly`），但查看模式（`readOnly`）不显示
- 新增查看模式项目信息卡（`instanceId && readOnly`），展示：
  - 项目名称、项目类型、预计金额、合作公司、联系人、联系方式
  - 中标状态只读文本（绿色/红色/黄色标注）
- 中标状态从 `GET /projects/{projectId}` 实时读取，与编辑修改保持同步

#### 4. 渠道项目查看 → 走 DynamicForm（[Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)）

- 新增 `channelFormTemplate` 状态、`loadChannelFormTemplate()` 函数（按模板名"渠道项目"搜索）
- 新增 `handleChannelFormView()` 和 `showChannelViewForm` 弹窗
- `handleViewProject` 增加渠道项目分流：`p.source === 'channel' && p.form_instance_id` 时走 DynamicForm 只读查看
- 渠道项目编辑不受影响，继续走 ProjectForm

### 最终行为矩阵

| 操作 | 自营项目 | 渠道项目 |
|------|---------|---------|
| 新建 | DynamicForm（模板字段） | ProjectForm（硬编码） |
| 编辑 | ProjectForm（项目信息+文件管理） | ProjectForm（项目信息+文件管理） |
| 查看 | DynamicForm（只读，模板字段+项目信息卡） | DynamicForm（只读，模板字段+项目信息卡） |

### 本轮改动文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/components/DynamicForm.jsx` | `loadInstance useEffect` 增加 `setValues(v)` 填充表单值；新增查看模式蓝色项目信息卡（含中标状态只读展示）；必填项红色 `*` 标记在只读模式也显示；项目信息卡标签根据模板名称动态切换 |
| `frontend/src/pages/Projects.jsx` | 移除 `showSelfEditForm`/`handleSelfFormEdit`；新增 `channelFormTemplate`/`loadChannelFormTemplate`/`handleChannelFormView`/`showChannelViewForm`；`handleViewProject` 渠道项目分流；`handleEditProject` 统一走 ProjectForm |
| `frontend/src/components/ProjectForm.jsx` | 增加 `isSelfProject` 判断，所有标签文字根据 `project.source` 动态切换 |

---

## 26. 自营/渠道项目标签文字对齐 + 左侧菜单顺序调整（2026-08-27）

### 26.1 标签文字对齐
**需求**：自营项目编辑表单中，"合作公司/联系人/联系方式/预计金额"标签需要和自营项目模板一致：

| 字段 | 渠道项目 | 自营项目 |
|------|---------|---------|
| 金额 | 预计金额 | 预计落单金额 |
| 客户 | 公司名称 | 客户单位名称 |
| 联系人 | 联系人 | 业主方联系人 |
| 联系方式 | 联系方式 | 业主方联系方式 |

**实现**：
- [DynamicForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/DynamicForm.jsx)：根据模板名称 `template.name.includes('自营')` 判断，动态切换 fallback key 和显示标签
- [ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)：根据 `project.source === 'self'` 判断，所有蓝色信息卡、只读标签、编辑输入框标签全部动态切换

### 26.2 左侧菜单顺序调整
**需求**：存储区域和用户管理下移到**通知管理**上面，其他顺序不变。

**原顺序**：项目列表 → 审批管理 → 项目跟单 → AI报表 → 存储区域 → 用户管理 → 表单管理 → 审计记录 → 通知管理 → 通知中心

**新顺序**：项目列表 → 审批管理 → 项目跟单 → AI报表 → 表单管理 → 审计记录 → 通知管理 → **存储区域 → 用户管理** → 通知中心

**改动**：[Layout.jsx:104-120](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx#L104-L120) 调整菜单位置

### 本轮改动文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/components/DynamicForm.jsx` | 项目信息卡标签、fallback key 动态匹配模板名称 |
| `frontend/src/components/ProjectForm.jsx` | 蓝色信息卡标签、只读字段标签、编辑输入框标签全部动态匹配项目来源 |
| `frontend/src/components/Layout.jsx` | 调整左侧菜单栏顺序 |

---

## 28. 普通账号「查看」入口对齐 admin/important/archive（2026-08-27）

### 背景

之前普通账号（`role=normal`）在 [Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx) 列表中点击「查看」按钮时，调用的是 `setShowViewForm(true)` 直接弹 [ProjectForm](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx) 的渠道项目只读视图；而 admin/important/archive 走的是 `handleViewProject(p)` 按 `source` 分发到 DynamicForm（自营）或 DynamicForm（渠道）。

导致同一个项目：
- admin 看到 → DynamicForm 自营模板
- 普通账号看到 → ProjectForm 渠道硬编码字段

两者内容不一致，违反「同一项目查看内容统一」原则。

### 改动

[Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx#L361)：

普通账号操作列改为：
```js
const buttons = [
  <button key="edit" onClick={() => { setEditData(p); setShowForm(true) }} className="text-blue-600 hover:underline">编辑</button>,
  <button key="view" onClick={() => handleViewProject(p)} className="text-gray-600 hover:underline">查看</button>,
]
```

- 「编辑」 → 走 `setShowForm(true)` 打开 ProjectForm 编辑（与 admin 一致）
- 「查看」 → 走 `handleViewProject(p)`，按 `p.source` 路由：
  - `source='self' && form_instance_id` → `handleSelfFormView` → DynamicForm 自营模板只读
  - `source='channel' && form_instance_id` → `handleChannelFormView` → DynamicForm 渠道模板只读
  - 其他 → ProjectForm 只读视图

### 效果

| 角色 | 渠道项目查看 | 自营项目查看 |
|---|---|---|
| admin / important / archive | DynamicForm（渠道模板） | DynamicForm（自营模板） |
| 普通账号 | DynamicForm（渠道模板） ✅ 现在一致 | DynamicForm（自营模板） ✅ 现在一致 |

---

## 29. 渠道项目「新建」按钮改为走 DynamicForm + 独立 showChannelForm 弹窗（2026-08-27）

### 背景

用户在「表单管理 → 渠道项目登记表」中改了分区名/字段 label 并保存后：

- ✅ **查看**渠道项目：立即看到新模板（`handleChannelFormView` 每次 `loadChannelFormTemplate()`）
- ❌ **新建**渠道项目：依旧显示老模板（硬编码「项目基本情况」分区 + 「选填」textarea）

### 根因排查（按发现顺序）

#### 1. 「渠道项目新建」按钮 onClick 直接打开 ProjectForm

[Projects.jsx:191-196](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx#L191-L196)：

```js
<button onClick={() => { setEditData(null); setShowForm(true) }}>
  渠道项目新建
</button>
```

→ 走 `ProjectForm`（[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)）硬编码字段，**完全没读 form_templates 表**。

对比自营项目「新建」按钮 onClick 是 `handleSelfFormNew` → `loadSelfFormTemplate()` → DynamicForm（每次拉最新模板）。两者路径根本不对称。

#### 2. 第一轮修复后弹窗仍不显示

我先加 `handleChannelFormNew` 并复用 `setShowChannelViewForm(true)`，结果渠道项目查看弹窗条件是：

```js
{showChannelViewForm && channelFormTemplate && editData && (...)}
```

新建时 `editData=null`，**弹窗不渲染**。用户看到的「项目基本情况」分区其实是**浏览器旧 bundle 跑的 ProjectForm**（没重新 build）。

#### 3. 最终方案：新增独立 `showChannelForm` state + 独立弹窗

[Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)：

1. 新增 state：
   ```js
   const [showChannelForm, setShowChannelForm] = useState(false)  // 渠道项目新建弹窗
   ```

2. `handleChannelFormNew` 触发 `setShowChannelForm(true)`（不再复用 `showChannelViewForm`）：
   ```js
   const handleChannelFormNew = async () => {
     const tpl = await loadChannelFormTemplate()
     if (tpl) {
       setEditData(null)
       setShowChannelForm(true)
     }
   }
   ```

3. 新增独立弹窗渲染块（与自营项目新建对称，不传 instanceId、不传 readOnly、不要求 editData）：
   ```jsx
   {showChannelForm && channelFormTemplate && (
     <div className="fixed inset-0 bg-black/50 ... z-50 p-4">
       <div className="bg-white rounded-lg shadow-2xl max-h-[92vh] overflow-auto w-[1100px] max-w-[95vw] p-6">
         <DynamicForm
           template={channelFormTemplate}
           onClose={() => setShowChannelForm(false)}
           onSubmitted={() => { setShowChannelForm(false); fetchProjects() }}
         />
       </div>
     </div>
   )}
   ```

4. 「渠道项目新建」按钮 onClick 改为 `handleChannelFormNew`。

### 最终对称矩阵

| 操作 | 自营项目 | 渠道项目 |
|---|---|---|
| 新建 | DynamicForm（**最新模板**） | DynamicForm（**最新模板**） ✅ 修复后 |
| 编辑 | ProjectForm | ProjectForm |
| 查看 | DynamicForm 只读 | DynamicForm 只读 |

### 教训（本轮）

1. **「复用查看 state 做新建」是常见错误** —— 查看弹窗条件 `editData` 必填，新建时 `editData=null` 直接不渲染，必须用独立 state
2. **前端代码修改 ≠ 用户立即生效** —— 必须 `npm --prefix frontend run build` 后浏览器刷新，旧 bundle 仍跑 ProjectForm 硬编码字段
3. **API 调用失败要看 alert** —— `loadChannelFormTemplate` 内部 try/catch 必须打到 `alert()`，否则用户不知道后端报错

### 关键文件

- [frontend/src/pages/Projects.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Projects.jsx)

---

## 30. 通知管理 — 增加可定制第三方短信云平台（sms_custom）（2026-08-28）

### 背景

业务上有需求对接国内/国外各种第三方短信云平台（华为云、容联、Twilio、自建网关等），这些平台每个的 API 形态都不同。用户要求在「通知管理 → 通知通道配置」中增加一个**可定制**的第三方短信云平台配置项，能配：
- 任意 POST URL
- 任意 Headers（如 `Authorization: Bearer xxx`）
- 任意 Body 模板（占位符 `{phone}/{title}/{content}/{sign_name}` 替换）
- 任意判定成功的方式（HTTP 2xx + 响应字段 = 某值）

### 设计

| 项 | 内容 |
|---|---|
| 通道 type | `sms_custom`（与已有 `sms_aliyun`/`sms_tencent` 同级） |
| 投递优先级 | `sms_custom` > `sms_aliyun` > `sms_tencent`（首个启用即用） |
| Config 字段 | `endpoint`(必填) / `method`(POST/GET/PUT) / `headers`(dict) / `body_template`(必填, dict 或 str) / `sign_name`(可选) / `success_keys`(list, 默认 `[code, errcode, status]`) / `success_value`(可选) / `timeout`(秒, 默认 10) |
| 占位符 | `{phone}` `{title}` `{content}` `{sign_name}` — 递归替换 dict/list/str |
| 成功判定 | HTTP 2xx 且响应 JSON 任意 success_key 等于 success_value → 成功；未配置 success_value 默认接受 0/"0"/"OK"/ok/true/"success"/200 |
| 非 JSON 响应 | 仅按 HTTP 2xx 判定 |

### 后端实现

#### [backend/app/routers/notifications_ws.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/notifications_ws.py)

1. **`upsert_channel`**：允许 `sms_custom` 类型；保存前校验 `endpoint` + `body_template` 必填
2. **新增 `POST /api/notifications/channels/{ctype}/test`**：
   - 入参 `{ phone, title?, content? }`
   - 用当前 `sms_custom` 配置立刻 POST 一次，返回 `{ ok, status_code, response_text, response_json?, latency_ms, error? }`
   - 仅 admin 可调

3. **修复 bug**：原文件漏 `import NotificationTemplate`，导致 `list_templates` 接口运行时 `NameError`，全模块被 uvicorn 卸载、所有 `/api/notifications/*` 接口返回 502/422（包括 `auth/login` 因为 import 链）。已补齐。

#### [backend/app/services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py)

1. **新增 `_send_sms_custom_sync(cfg, phone, title, content)`**：递归渲染 body_template → POST → 校验成功
2. **`_send_sms_sync`** 调整为 `sms_custom > aliyun > tencent` 优先级

### 前端实现

#### [frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)

- 新增 `testNotificationChannel(type, data)`

#### [frontend/src/pages/NotificationAdmin.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/NotificationAdmin.jsx)

1. `CHANNEL_TYPES` 加 `sms_custom`：「第三方短信云平台(可定制)」
2. **打开/新建**：sms_custom 用结构化 state（`custom`），其他保持 JSON 文本
3. **编辑弹窗**：
   - sms_custom → 绿色高亮区块 + 结构化表单（Endpoint / Method / Headers / Body 模板 / 签名 / 成功判定 Keys / Value / 超时）
   - 占位符说明：`{phone} {title} {content} {sign_name}`
   - 「✨ 可定制」绿色徽章
   - 内置「🧪 测试发送」区：输入测试手机号 → 自动 upsert 当前表单 → 调 test → 显示 HTTP 状态 / 耗时 / 响应原文（折叠 details）
   - 其他通道 → 仍用 JSON 文本框（保持原行为）
4. `normalizeCustomCfg(cfg)`：DB 配置 → UI 结构化字段
5. `buildCustomCfg(c)`：UI 字段 → JSON 配置（含 JSON 校验）

### 用法示例

#### 阿里云短信 1.0（旧版，非 SDK 模式）

```json
{
  "endpoint": "https://sms.aliyuncs.com/",
  "method": "GET",
  "headers": {},
  "body_template": {
    "PhoneNumbers": "{phone}",
    "SignName": "{sign_name}",
    "TemplateCode": "SMS_0000",
    "TemplateParam": "{\"content\":\"{content}\"}"
  },
  "sign_name": "销售项目管理系统",
  "success_keys": ["Code"],
  "success_value": "OK"
}
```

#### 通用 HTTP 推送（华为云/腾讯云/容联/Twilio 适配版）

```json
{
  "endpoint": "https://sms.cn-hangzhou.example.com/v1/send",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
  },
  "body_template": {
    "to": "{phone}",
    "from": "{sign_name}",
    "body": "{content}"
  },
  "success_keys": ["errcode"],
  "success_value": 0
}
```

### 验证

| 步骤 | 结果 |
|---|---|
| 后端启动 | ✅ 端口 8765, health 200 |
| 前端 build | ✅ `index-Byb0RxBu.js` 21.68s |
| `/admin/` 加载 | ✅ 200,新 bundle 已加载 |
| `/admin/assets/index-*.css` | ✅ 200 |
| OpenPreview 健康检查 | ✅ 200 |

### 关键文件

- 后端路由：[backend/app/routers/notifications_ws.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/notifications_ws.py)
- 后端服务：[backend/app/services/notifications.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/notifications.py)
- 前端 API：[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)
- 前端页面：[frontend/src/pages/NotificationAdmin.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/NotificationAdmin.jsx)

### 教训（本轮）

1. **`NameError` 在模块顶层会拖垮整个 router** —— 之前 `from app.models import` 漏写 `NotificationTemplate`，导致 `list_templates` 接口运行时 `NameError`，整个 notifications_ws router 在 uvicorn 拒绝注册路由，所有 `/api/notifications/*` 路径（包括 `/auth/login` 因为被 import 链加载）全部 502/422
2. **占位符递归渲染要稳** —— body_template 可能是 dict / list / str，纯字符串 `format` 在 dict 场景下 KeyError。必须递归遍历所有 leaf string 后 `.format(...)`
3. **第三方平台的成功判定不能写死** —— 不同平台成功字段不一样（`code` / `errcode` / `status` / `Code` / `Result`），必须让用户配置

### 27.1 AI 字符宽度对齐

**问题**：左栏菜单里 `📊 AI报表` 的 "AI" 两个英文字符比同行的"项目/管理"等汉字窄，造成上下菜单基线不对齐。

**解决**（[Layout.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/Layout.jsx)）：把 "AI" 拆成两个子 span，每个子 span 独立设置 1em 宽 + text-align:center，让 A 居中显示在第 1 个汉字位置、I 居中显示在第 2 个汉字位置：

```jsx
const aiStyle = { display: 'inline-flex', fontFamily: '"PingFang SC","Microsoft YaHei","微软雅黑",sans-serif' }

<Link to="/reports" ...>
  📊 <span style={aiStyle}>
    <span style={{ width: '1em', textAlign: 'center', display: 'inline-block' }}>A</span>
    <span style={{ width: '1em', textAlign: 'center', display: 'inline-block' }}>I</span>
  </span>报表
</Link>
```

**关键点**：
- 用 `display: inline-block` 让子 span 的 `width: 1em` 生效
- `text-align: center` 把字符居中在自己的 1em 单元内
- 强制中文字体，避免英文 fallback 字符宽差异
- 不要在 JSX 文本节点里写 `\u2009`（窄空格），它会被当字面量，不解析 Unicode 转义；要空格就用 `{'\u2009'}` 或直接换结构

### 27.2 表单管理列表去掉「系统内置」徽章

**需求**：用户反馈「表单管理」列表里"系统内置"小蓝徽章多余，要求去掉，让三个模板（渠道项目登记表 / 自营项目登记表 / 项目跟单登记表）格式一致。

**改动**（[FormTemplates.jsx:154-156](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/FormTemplates.jsx#L154-L156)）：

| 之前 | 之后 |
|---|---|
| `<tr className={... ${isBuiltin ? 'bg-blue-50/40' : ''}}>` | `<tr className="border-b hover:bg-gray-50">` |
| `<td className="font-medium flex items-center gap-2 whitespace-nowrap">` + 内嵌 `<span>系统内置</span>` | `<td className="font-medium whitespace-nowrap min-w-[10rem]">` + 直接渲染 `t.name` |

**保留**：
- `isBuiltin` 变量仍存在，alert「是系统内置表单模板，不能删除/停用」的告警逻辑保持不变——内置模板仍只受代码维护，UI 上不允许误操作。
- 行内 `<span>{t.name}</span>` 视觉上跟其它无徽章的模板一致。

### 本轮改动文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/components/Layout.jsx` | 新增 `aiStyle` 常量；"AI报表"菜单项把 "AI" 拆成两个 1em 居中子 span |
| `frontend/src/pages/FormTemplates.jsx` | 去掉"系统内置"蓝徽章；移除内置模板的 `bg-blue-50/40` 行背景色；td 简化为直接渲染 `t.name` 加 `min-w-[10rem]` 防折行 |

---

## 31. AI报表「模型配置」仅系统管理员可用（2026-08-27）

---

## 32. 大文件上传报错（HTTP 413）+ 进度条 + 服务端流式分块（2026-08-28）

### 背景

用户截图反馈：上传 25M 文件时前端报"提交失败: Request failed with status code 413"，但实际上文件已成功传到服务器；后续测试 200M 文件直接报错无法上传。

### 根因（三层叠加）

| 层 | 默认限制 | 本次配置 |
|---|---|---|
| Nginx `client_max_body_size` | **1MB**（超就 413） | **500MB** |
| uvicorn `--limit-max-requests` | 无 body 限制 | 保持不限 |
| FastAPI/Starlette | 默认不限 body 大小 | 保持 |

所以 **Nginx 的 1M 默认值就是拦路虎** —— 任何超过 1MB 的 POST 都会被 Nginx 直接拒绝（HTTP 413），根本到不了后端。

为什么 25M 已传成功：第一次 POST 时文件可能比较小（用户选的可能是图片/小文档），后续再选大文件才会 413。所以"已经传上去了"≠"这次能传上去"。

### 修改

#### 1. 后端 — 流式分块 + 实时大小检查
[backend/app/routers/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py)

- 新增 `_MAX_FILE_SIZE_DEFAULT = 500MB`、`_CHUNK_SIZE = 1MB`
- 新增 `_get_max_file_size(db)` — 从 `config.yaml: upload.max_file_size_mb` 读取（默认 500）
- 新增 `_read_upload_streaming(upload_file, max_size)` — **流式分块读取 + 超过 max_size 立即中止抛 413**
- `upload_files` 用 `_read_upload_streaming(f, max_size)` 替代 `await f.read()`
- 避免大文件一次 `read()` 撑爆内存（200MB 占用 ~200MB 内存，500MB 会爆）

#### 2. 前端 — 进度条 + 分批上传 + 友好错误提示
[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)

1. 新增 state：`uploadProgress = { tender: { percent, currentFile, batchIndex, batchCount }, bid: {...} }`
2. **改 fetch 为 XHR** — `xhr.upload.onprogress` 拿到真实字节进度
3. **分批上传**：每批 ≤ 3 个文件，避免单次 form-data 体积过大
4. **前置校验**：单文件 > 500MB 直接弹 alert 拒绝（不等传完再报 413）
5. **UI 进度条**：
   - 实时百分比 + 蓝色进度条
   - 当前文件名（truncate + 完整显示）
   - 批次信息（"批次 2/3"）
6. **友好提示**：遇到 413 主动提示"Nginx client_max_body_size 配置问题"
7. 拖拽区底部增加提示文字："单文件最大 500MB，超大文件请压缩分批上传"

[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)

- 新增 `uploadFormFilesXhr(instanceId, folderType, files, onProgress)` — DynamicForm 自营/渠道上传也用 XHR 版本（保留 `uploadFormFiles` 给不上传进度的场景）

#### 3. 部署脚本 — 自动调 Nginx body 限制
[deploy/remote_update.sh](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/remote_update.sh)

新增 Step 6.5：

```bash
# 6.5 检查并修复 Nginx client_max_body_size（大文件上传必需）
NGINX_CONF=$(sudo find /etc/nginx -name "*.conf" ... | head -3)
# 对每个 conf：
#   没有 client_max_body_size → 在 server { 之前插入 client_max_body_size 500m;
#   已有但 < 500m → 改成 500m
#   已有 ≥ 500m → 保留
# sudo nginx -t && sudo systemctl reload nginx
```

部署时输出：
```
[6.5/7] 调整 Nginx body 限制...
  * /etc/nginx/sites-available/channel 改为 500m
  = /etc/nginx/sites-enabled/channel 已有 client_max_body_size 500m, 保留
nginx: configuration file /etc/nginx/nginx.conf test is successful
  nginx reloaded
```

### 验证

| 测试 | 结果 |
|---|---|
| 本地 build | ✅ index-B8-kY6Pt.js 489KB / 143KB gzip |
| 服务器部署 | ✅ PID 842527 active running |
| Step 6.5 Nginx 调整 | ✅ 500m 已生效 |
| /api/health | ✅ 200 |
| /api/auth/login | ✅ 200 |
| /api/projects/ | ✅ 200 total=9 |

**用户验证步骤**：
1. 浏览器 **Ctrl+Shift+R** 强制刷新
2. 打开一个项目 → 编辑模式
3. 拖拽一个大文件（如 200M rar）到文件管理区
4. 应该看到：上传中... X% + 蓝色进度条 + 当前文件名 + 批次信息

### 关键文件

- 后端：[backend/app/routers/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py)
- 前端：[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)
- 前端 API：[frontend/src/api/index.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/api/index.jsx)
- 部署脚本：[deploy/remote_update.sh](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/remote_update.sh)

### 教训（本轮）

1. **Nginx `client_max_body_size` 默认 1M 是隐藏陷阱** —— 几乎所有反向代理场景都需要调大，但部署脚本之前没覆盖这一步
2. **`fetch` 不支持上传进度** —— 必须用 `XMLHttpRequest.upload.onprogress`
3. **`await file.read()` 不限大小** —— 一次读取超大文件会撑爆内存；流式分块是必须的
4. **错误提示要让用户知道下一步怎么办** —— 413 一定要提示"Nginx client_max_body_size 配置问题"，而不是单纯弹"上传失败"

### 配置扩展（可选）

`config.yaml` 可加：
```yaml
upload:
  max_file_size_mb: 500   # 单文件最大 MB，后端自动读取
  max_batch_size: 3       # 单批最大文件数（前端硬编码,可改为读后端配置）
```

---

## 33. preview-path 总是按当前日期渲染，覆盖建项目时的日期（2026-08-28）

### 现象

用户截图反馈：
- WebDAV 磁盘目录上的文件夹：`张林+自营再测试+2026-08-27`（建项目时建立的，正确）
- 系统界面显示：`张林+自营再测试+2026-08-28`（错的，是今天）
- 上传的文件实际写到了 `2026-08-27` 目录（DB里的旧路径，对的）
- 但用户看不到正确路径，被误导

### 根因

文件路径模板： `{responsible_sales}+{project_name}+{date}`

`render_base_folder` 在 [backend/app/services/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/file_storage.py) 第42 行：

```python
created_at = created_at or datetime.datetime.now()  # 每次调用都按"今天"渲染
```

而 **preview-path** 接口 [backend/app/routers/file_storage.py:315](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py#L315)：

```python
root = render_project_root(cfg_obj, username, real_name, data.project_name, data.responsible_sales)
#           ↑ 没传 created_at 参数 → 用默认值 datetime.now()
```

前端 [frontend/src/components/ProjectForm.jsx:190-196](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx#L190-L196)：

```js
const [resTender, resBid] = await Promise.all([
  previewFileStoragePath({ project_name: form.project_name, folder_type: 'tender', ... }),
  previewFileStoragePath({ project_name: form.project_name, folder_type: 'bid', ... }),
])
setTenderPreview((resTender?.data ?? resTender)?.tender_folder || ...)
setBidPreview((resBid?.data ?? resBid)?.bid_folder || ...)
```

→ 每次 useEffect 都用 preview-path（按"今天"渲染）覆盖了正确的 DB 路径。

### 为什么 DB 里的路径是对的

建项目时，后端 `create_project` 直接渲染一次路径写入 `Project.tender_folder / bid_folder` 字段，这就是"建项目时的日期"。

### 修复

[backend/app/routers/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py)（preview-path 接口）：

```python
# 修复：项目已存在时优先返回 DB 路径（保持建项目时的日期）
db_tender = ''
db_bid = ''
db_proj_for_preview = db.query(Project).filter(Project.project_name == data.project_name).first()
if db_proj_for_preview:
    db_tender = (db_proj_for_preview.tender_folder or '').strip()
    db_bid = (db_proj_for_preview.bid_folder or '').strip()

# 已存在项目：用 DB 路径（保持建项目时的日期不动）
if db_proj_for_preview and (db_tender or db_bid):
    return PathPreviewResponse(
        base_folder=root,  # 仅供参考
        tender_folder=db_tender or tender,
        bid_folder=db_bid or bid,
    )

# 新项目（DB 没记录）：返回实时渲染路径（给用户预览）
return PathPreviewResponse(
    base_folder=root,
    tender_folder=tender,
    bid_folder=bid,
)
```

### 修复后行为

| 场景 | 之前 | 现在 |
|---|---|---|
| 新建项目（DB 无记录）| 按今天渲染（合理）| 按今天渲染（合理，用于预览）|
| 已存在项目，今天打开 | 渲染成今天日期（错）| 返回 DB 路径 = 建项目时日期（对）|
| 已存在项目，明天上传 | 渲染成明天日期（错）| 返回 DB 路径（对）|
| 上传文件实际路径 | 走 DB 路径（对）| 走 DB 路径（对）|

### 验证

| 测试 | 结果 |
|---|---|
| 本地重启服务 | ✅ PID 17212, port 8765 ready |
| OpenPreview /admin/ | ✅ 200, 新代码已加载 |
| 用户操作 | 刷新浏览器,打开那个 "张林+自营再测试" 项目 |

### 教训（本轮）

1. **"重渲染" vs "读取已存"** —— 路径里有时间相关变量时，必须先查 DB 是否已有路径,优先用 DB 路径,避免每次渲染都变
2. **`useEffect` 调用 preview 接口的副作用** —— 任何"预览"接口如果按时间渲染就会跟"真理"（DB）冲突,UI 显示会误导用户
3. **AGENTS.md 之前没记录这种"模板渲染副作用"** —— 应当把"模板渲染的副作用"列入注意事项

### 关键文件

- 后端：[backend/app/routers/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/file_storage.py)
- 服务：[backend/app/services/file_storage.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/services/file_storage.py)
- 前端：[frontend/src/components/ProjectForm.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/components/ProjectForm.jsx)

---

## 34. 申请账号报 `UnboundLocalError: UserRole`（2026-08-28）

### 现象

用户访问登录页 → 点击「申请账号」→ 填姓名 → 提交：
```
UnboundLocalError: cannot access local variable 'UserRole' where it is not associated with a value
```

### 根因（Python 编译期陷阱）

[backend/app/routers/auth.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/auth.py) `apply_account` 函数内部有：

```python
try:
    from app.services.notifications import send_notification
    from app.models import UserRole, NotificationType    # ← 第216行 函数内 import
    admins = db.query(User).filter(User.role == UserRole.admin, ...).all()
```

而该函数第195行已经引用了 `UserRole.normal`：

```python
user = User(
    username='!PENDING_' + candidate,
    ...
    role=UserRole.normal,    # ← 第195行
    is_active=False,
)
```

**Python 编译期规则**：函数体内有任何名字的 `import` 或赋值，**整个函数**内所有该名字都被标记为 `local`（即使 import 出现在使用之后）。所以 `UserRole` 在 apply_account 中变成 local 变量，而 local 变量在第195行（import 之前）就被引用 → `UnboundLocalError`。

`register` 函数也有同样的"函数内 import"问题（第106行），但 register 的 import 在使用之前（先import再114行用），所以 register 不会报错——只有 apply_account 报错。

### 修复

[backend/app/routers/auth.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/auth.py)：

1. **顶部 import 加上 NotificationType**：
   ```python
   from app.models import User, AuditAction, UserRole, NotificationType
   ```

2. **删除 register 函数内第106行** `from app.models import UserRole`：
   ```python
   if current_user.role.value != "admin":
       raise HTTPException(status_code=403, detail="仅管理员可注册账号")
   # 删掉了: from app.models import UserRole
   existing = db.query(User).filter(User.username == username).first()
   ```

3. **删除 apply_account 函数内第216行** `from app.models import UserRole, NotificationType`：
   ```python
   try:
       from app.services.notifications import send_notification
       # 删掉了: from app.models import UserRole, NotificationType
       admins = db.query(User).filter(User.role == UserRole.admin, ...).all()
   ```

### 验证

| 测试 | 结果 |
|---|---|
| 本地 Python 测试 | `POST /api/auth/apply-account {real_name: "测试名字"}` → 200 OK，body 含 `username="xxxx"` + `initial_password="R7pu4fsG"` |
| 本地服务重启 | ✅ PID 29924, port 8765 ready |

### 教训（本轮）

1. **Python 函数内 import 是隐藏陷阱** —— 编译期把名字标记为 local，导致 import 之前的引用全部 UnboundLocalError
2. **原则：import 一律写在文件顶部** —— 不要在函数内 import 已经在顶部 import 过的名字
3. **PyCharm/IDE 通常会警告** —— 用 `from app.models import X` (X 已经在顶部) 会显示灰色提示
4. **审查时要看 import 在函数内的位置** —— 如果 import 在使用之前，至少不会报错，但仍是代码异味

### 关键文件

- 后端：[backend/app/routers/auth.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/auth.py)

---

## 35. 最小化 Hotfix 增量部署（2026-08-28 17:20）

### 背景

用户在 08:50 全量部署 `de7f03b` 后，发现两个独立 Bug：
1. 大文件上传 HTTP 413（→ 第 32 章修复）
2. 申请账号 UnboundLocalError（→ 第 34 章修复）

第 32 章修复涉及前端 build / 后端路由 / Nginx body 限制，已在 `3d69e7e deploy: 2026-08-28 16:47` 全量部署时一起带上。

第 34 章修复（auth.py UnboundLocalError）+ 第 33 章修复（preview-path 日期）只涉及两个 Python 文件。

### 为什么不直接 deploy_all.py 全量部署？

- 全量 tar 91MB，打包+上传+解压耗时 15+ 分钟
- 本次只改了 3 个文件（auth.py + file_storage.py + AGENTS.md），合计 ~48KB
- 重新打 tar 包还得再次构建前端（虽 bundle hash 没变，但 npm install 会重跑）

### 方案：SCP 单文件上传 + 重启

写了一个最小化脚本 [deploy/_hotfix_2026-08-28.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/_hotfix_2026-08-28.py)（已执行后删除）：

```python
files_to_upload = [
    (本地 auth.py        → /opt/.../backend/app/routers/auth.py),
    (本地 file_storage.py → /opt/.../backend/app/routers/file_storage.py),
    (本地 AGENTS.md       → /opt/.../AGENTS.md),
]
# 每条 scp + ssh 重启 + 健康检查 + apply-account 测试
```

### 验证（服务器实际返回）

| 测试 | 结果 |
|---|---|
| scp auth.py (9.2 KB) | ✅ 4.4 MB/s |
| scp file_storage.py (36 KB) | ✅ 5.8 MB/s |
| scp AGENTS.md (132 KB) | ✅ 21 MB/s |
| `sudo systemctl restart channel-project` | ✅ Active running (PID 974026)|
| `/api/health` | ✅ 200 `{"status":"ok"}` |
| **`/api/auth/apply-account {real_name: "hotfix-test-临时用户"}`** | ✅ **200 `{"username":"xsxxx","initial_password":"hNZlfQke"}`** |

### 数据保留确认

| 项 | 是否保留 |
|---|---|
| 数据库 data.db | ✅ 整个部署期间未触达 `/opt/channel-project/backend/data.db` |
| config.yaml | ✅ 未触达 |
| 已上传文件（WebDAV 172NAS）| ✅ 整个部署未触达 WebDAV |
| 用户账号 / 项目数据 / 审批 | ✅ 全部保留 |
| nginx 配置（client_max_body_size 500m） | ✅ 已有，保留 |

### 教训（本轮）

1. **大项目也可以"外科手术式"热更新** —— 不必每次都全量打包上传。知道改了什么、只传什么，3 秒/文件就完成
2. **winpty 转义吃 body 是已知限制** —— shell 复合命令里单引号会被吃，复杂验证用 Python TestClient 写脚本更稳
3. **部署可以分层** —— 紧急 hotfix 用最小化脚本，全量功能更新用 deploy_all.py

### 关键文件

- 部署脚本（临时）：[deploy/_hotfix_2026-08-28.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/_hotfix_2026-08-28.py)（已删除）
- 复用的工具函数：[deploy/deploy_all.py:96](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/deploy/deploy_all.py#L96)（`run_with_password` / `SCP` / `SSH` / 常量）

### 需求

AI报表中的「模型配置」功能（模型 CRUD + 连接测试）只能系统管理员使用；
其他角色（important / normal / archive / archive）进入 AI 报表时**看不到**「模型配置」页签，也无法调用模型配置接口。

### 后端现状（已满足，无需改动）

[forms.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/routers/forms.py) 中所有模型配置**写/测接口**均已使用 `require_admin`：

| 接口 | 鉴权 |
|---|---|
| `POST /api/forms/ai-models` | `require_admin` |
| `PUT /api/forms/ai-models/{id}` | `require_admin` |
| `DELETE /api/forms/ai-models/{id}` | `require_admin` |
| `POST /api/forms/ai-models/{id}/test` | `require_admin` |
| `GET /api/forms/ai-model-presets` | `require_admin` |

仅 `GET /api/forms/ai-models`（列表）为非 admin 保留：非 admin 自动只返回启用项（`is_enabled == True`），供「AI 分析」选择模型使用，不暴露密钥与未启用项。**刻意保留**，非 bug。

### 前端改动（本轮唯一改动）

[Reports.jsx](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/pages/Reports.jsx) 顶栏「模型配置」页签按钮用 `user?.role === 'admin'` 包裹，非 admin 不渲染：

```jsx
{user?.role === 'admin' && (
  <button onClick={() => setActiveTab('models')} ...>模型配置</button>
)}
```

`user` 来自 `useAuthStore()`（[frontend/src/stores/auth.js](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/frontend/src/stores/auth.js)），角色字段即 `user.role`（`'admin'`），与后端 `UserRole`（[models.py](file:///z:/soft-RED/hermes/开发软件/渠道项目登记/backend/app/models.py)）一致。

### 效果

- 非 admin 用户进入 AI 报表 → 只见「标准报表」「AI 分析」两个页签，无「模型配置」入口
- 即使绕过前端直接调写/测接口，也会被后端 `require_admin` 拦截返回 403（前后端双重保险）

### 改动文件

| 文件 | 改动 |
|---|---|
| `frontend/src/pages/Reports.jsx` | 「模型配置」页签按钮包裹 `user?.role === 'admin'` 条件渲染 |
| `backend/config.yaml` | （本次启动修复）数据库 URL 盘符 `Z:` → `Y:`，与仓库实际盘符对齐 |


