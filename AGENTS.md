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

- **需求**：跟单弹窗底部的「+ 添加字段」按钮不要；侧栏「V2.0」不要换行
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

## 17. 用户手册：销售项目管理系统V2.0（2026-08-20）

### 需求

生成 Word 版本用户手册，覆盖「用户登录 → 申请 → 新建项目 → 跟单 → 审批」全流程，以普通账号和重要账号 2 个角色为例。

### 文档信息

| 项目 | 内容 |
|---|---|
| 文件名 | `销售项目管理系统V2.0_用户手册.docx` |
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
  - 桌面原始：`C:\Users\jwang\Desktop\销售项目管理系统V2.0_用户手册.docx`
  - 项目目录：`Z:\soft-RED\hermes\开发软件\渠道项目登记\销售项目管理系统V2.0_用户手册.docx`
  - **仓库内**：`销售项目管理系统V2.0_用户手册.docx`（已 commit `a40d57c`）

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

### 明日继续建议

优先继续这 3 项：

1. 把 `AI 分析` 从当前结构化预览升级为真实模型调用
2. 增加模型测速结果排序/最近一次测试时间展示
3. 顺手修一下 `backend/start_server.py`，改为使用当前工作目录与 `.venv_local`，避免后续再次踩旧盘符问题
