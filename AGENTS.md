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

