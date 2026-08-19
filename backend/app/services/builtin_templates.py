"""内置表单模板定义 — 与 ProjectForm.jsx 字段定义 100% 一致

启动时自动同步到 form_templates 表，确保所见即所得：
  - 渠道项目登记表（用于项目列表的"新建项目"）
  - 自营项目登记表（用于项目列表的"自营项目新建"，文件存储在独立目录"自营项目/"）

字段分区（严格对齐 ProjectForm.jsx）：
  1. 项目基本信息（9 项 2 列网格）
  2. 合作基本情况（10 项 2 列网格）
  3. 项目基本情况（1 项 textarea）
  4. 文件管理（2 项 2 列网格）
"""

CHANNEL_PROJECT_TEMPLATE = {
    'name': '渠道项目登记表',
    'description': '渠道项目登记表单（系统内置，与项目列表的"新建项目"完全一致）',
    'storage_sub_path': '',  # 使用 FileStorageConfig 默认路径
    'storage_zone_id': 1,   # 使用默认存储区域（启动时迁移旧配置得到）
    'fields': [
        # — 区域 1: 项目基本信息 —
        {'id': 'pf_1', 'type': 'text',     'label': '项目名称',         'key': 'project_name',          'required': True,  'placeholder': '请输入项目名称', 'section': '项目基本信息'},
        {'id': 'pf_2', 'type': 'text',     'label': '责任销售',         'key': 'responsible_sales',     'required': True,  'placeholder': '请输入责任销售姓名（用于文件夹命名）', 'section': '项目基本信息'},
        {'id': 'pf_3', 'type': 'text',     'label': '项目编号',         'key': 'project_code',           'required': False, 'placeholder': '选填', 'section': '项目基本信息'},
        {'id': 'pf_4', 'type': 'select',   'label': '项目类型',         'key': 'project_type',           'required': True,  'options': ['信息化', '智能化', '机电消防', '软件开放', '系统运维', 'XC/SM', '军队武警', '其他'], 'section': '项目基本信息'},
        {'id': 'pf_5', 'type': 'number',   'label': '预计金额',         'key': 'expected_amount',        'required': True,  'placeholder': '0.00', 'section': '项目基本信息'},
        {'id': 'pf_6', 'type': 'date',     'label': '招标时间',         'key': 'tender_time',            'required': False, 'section': '项目基本信息'},
        {'id': 'pf_7', 'type': 'date',     'label': '投标时间',         'key': 'bid_time',               'required': False, 'section': '项目基本信息'},
        {'id': 'pf_8', 'type': 'text',     'label': '业主联系人',       'key': 'owner_contact_person',   'required': False, 'placeholder': '选填', 'section': '项目基本信息'},
        {'id': 'pf_9', 'type': 'text',     'label': '业主联系方式',     'key': 'owner_contact_info',     'required': False, 'placeholder': '选填', 'section': '项目基本信息'},

        # — 区域 2: 合作基本情况 —
        {'id': 'pf_10', 'type': 'text',    'label': '公司名称',         'key': 'partner_company',        'required': True,  'placeholder': '请输入公司名称', 'section': '合作基本情况'},
        {'id': 'pf_11', 'type': 'text',    'label': '公司地址',         'key': 'company_address',        'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_12', 'type': 'text',    'label': '主要资质',         'key': 'main_qualification',     'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_13', 'type': 'text',    'label': '法定代表',         'key': 'legal_representative',   'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_14', 'type': 'text',    'label': '联系人',           'key': 'contact_person',         'required': True,  'placeholder': '请输入联系人', 'section': '合作基本情况'},
        {'id': 'pf_15', 'type': 'text',    'label': '联系方式',         'key': 'contact_info',           'required': True,  'placeholder': '请输入联系方式', 'section': '合作基本情况'},
        {'id': 'pf_16', 'type': 'select',  'label': '合作模式',         'key': 'cooperation_mode',       'required': False, 'options': ['长期合作', '短期合作'], 'section': '合作基本情况'},
        {'id': 'pf_17', 'type': 'select',  'label': '费用模式',         'key': 'fee_mode',               'required': False, 'options': ['互免', '收费'], 'section': '合作基本情况'},
        {'id': 'pf_18', 'type': 'select',  'label': '中标状态',         'key': 'win_bid_status',         'required': False, 'options': ['进行中', '中标', '未中标'], 'section': '合作基本情况'},
        {'id': 'pf_19', 'type': 'select',  'label': '是否SM',           'key': 'is_sm',                  'required': False, 'options': ['是', '否'], 'section': '合作基本情况'},

        # — 区域 3: 项目基本情况 —
        {'id': 'pf_20', 'type': 'textarea', 'label': '项目基本情况',   'key': 'project_overview',       'required': False, 'placeholder': '选填', 'section': '项目基本情况'},

        # — 区域 4: 文件管理 —
        {'id': 'pf_21', 'type': 'file',    'label': '招标资料',         'key': 'tender_file',            'required': False, 'accept': '.pdf,.doc,.docx,.xls,.xlsx', 'multiple': True, 'section': '文件管理'},
        {'id': 'pf_22', 'type': 'file',    'label': '投标文档',         'key': 'bid_file',               'required': False, 'accept': '.pdf,.doc,.docx,.xls,.xlsx', 'multiple': True, 'section': '文件管理'},
    ],
}

SELF_PROJECT_TEMPLATE = {
    'name': '自营项目登记表',
    'description': '自营项目登记表单（系统内置，与项目列表的"自营项目新建"完全一致；文件存储在 NAS 独立目录"自营项目/"）',
    'storage_sub_path': '自营项目',
    'storage_zone_id': 1,    # 使用默认存储区域（启动时迁移旧配置得到）
    'fields': [
        # 完全复用渠道项目的字段集（深拷贝避免引用共享）
        {'id': 'pf_1', 'type': 'text',     'label': '项目名称',         'key': 'project_name',          'required': True,  'placeholder': '请输入项目名称', 'section': '项目基本信息'},
        {'id': 'pf_2', 'type': 'text',     'label': '责任销售',         'key': 'responsible_sales',     'required': True,  'placeholder': '请输入责任销售姓名（用于文件夹命名）', 'section': '项目基本信息'},
        {'id': 'pf_3', 'type': 'text',     'label': '项目编号',         'key': 'project_code',           'required': False, 'placeholder': '选填', 'section': '项目基本信息'},
        {'id': 'pf_4', 'type': 'select',   'label': '项目类型',         'key': 'project_type',           'required': True,  'options': ['信息化', '智能化', '机电消防', '软件开放', '系统运维', 'XC/SM', '军队武警', '其他'], 'section': '项目基本信息'},
        {'id': 'pf_5', 'type': 'number',   'label': '预计金额',         'key': 'expected_amount',        'required': True,  'placeholder': '0.00', 'section': '项目基本信息'},
        {'id': 'pf_6', 'type': 'date',     'label': '招标时间',         'key': 'tender_time',            'required': False, 'section': '项目基本信息'},
        {'id': 'pf_7', 'type': 'date',     'label': '投标时间',         'key': 'bid_time',               'required': False, 'section': '项目基本信息'},
        {'id': 'pf_8', 'type': 'text',     'label': '业主联系人',       'key': 'owner_contact_person',   'required': False, 'placeholder': '选填', 'section': '项目基本信息'},
        {'id': 'pf_9', 'type': 'text',     'label': '业主联系方式',     'key': 'owner_contact_info',     'required': False, 'placeholder': '选填', 'section': '项目基本信息'},

        {'id': 'pf_10', 'type': 'text',    'label': '公司名称',         'key': 'partner_company',        'required': True,  'placeholder': '请输入公司名称', 'section': '合作基本情况'},
        {'id': 'pf_11', 'type': 'text',    'label': '公司地址',         'key': 'company_address',        'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_12', 'type': 'text',    'label': '主要资质',         'key': 'main_qualification',     'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_13', 'type': 'text',    'label': '法定代表',         'key': 'legal_representative',   'required': False, 'placeholder': '选填', 'section': '合作基本情况'},
        {'id': 'pf_14', 'type': 'text',    'label': '联系人',           'key': 'contact_person',         'required': True,  'placeholder': '请输入联系人', 'section': '合作基本情况'},
        {'id': 'pf_15', 'type': 'text',    'label': '联系方式',         'key': 'contact_info',           'required': True,  'placeholder': '请输入联系方式', 'section': '合作基本情况'},
        {'id': 'pf_16', 'type': 'select',  'label': '合作模式',         'key': 'cooperation_mode',       'required': False, 'options': ['长期合作', '短期合作'], 'section': '合作基本情况'},
        {'id': 'pf_17', 'type': 'select',  'label': '费用模式',         'key': 'fee_mode',               'required': False, 'options': ['互免', '收费'], 'section': '合作基本情况'},
        {'id': 'pf_18', 'type': 'select',  'label': '中标状态',         'key': 'win_bid_status',         'required': False, 'options': ['进行中', '中标', '未中标'], 'section': '合作基本情况'},
        {'id': 'pf_19', 'type': 'select',  'label': '是否SM',           'key': 'is_sm',                  'required': False, 'options': ['是', '否'], 'section': '合作基本情况'},

        {'id': 'pf_20', 'type': 'textarea', 'label': '项目基本情况',   'key': 'project_overview',       'required': False, 'placeholder': '选填', 'section': '项目基本情况'},

        {'id': 'pf_21', 'type': 'file',    'label': '招标资料',         'key': 'tender_file',            'required': False, 'accept': '.pdf,.doc,.docx,.xls,.xlsx', 'multiple': True, 'section': '文件管理'},
        {'id': 'pf_22', 'type': 'file',    'label': '投标文档',         'key': 'bid_file',               'required': False, 'accept': '.pdf,.doc,.docx,.xls,.xlsx', 'multiple': True, 'section': '文件管理'},
    ],
}

# 内置模板名集合（用于前端识别只读、禁止删除/停用）
BUILTIN_TEMPLATE_NAMES = {CHANNEL_PROJECT_TEMPLATE['name'], SELF_PROJECT_TEMPLATE['name']}