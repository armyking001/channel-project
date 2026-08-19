# Agents 记录 — 渠道项目登记

本文档记录本项目中由 Agent 实施的关键功能与改动。

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

