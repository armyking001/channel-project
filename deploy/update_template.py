"""更新自建项目模板 - 修正字段、分区、名称和存储路径"""
import requests
import json

BASE = 'http://127.0.0.1:8765/api'
PROXIES = {'http': None, 'https': None}

def main():
    # 登录
    r = requests.post(f'{BASE}/auth/login', data={'username': 'admin', 'password': 'akwj210627'}, proxies=PROXIES)
    token = r.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 新的模板数据 - 对齐 projectFormTemplate.js
    new_fields = [
        # — 区域 1: 项目基本信息 —
        {"id": "pf_1", "type": "text", "label": "项目名称", "key": "project_name", "required": True, "placeholder": "请输入项目名称", "section": "项目基本信息"},
        {"id": "pf_2", "type": "text", "label": "责任销售", "key": "responsible_sales", "required": True, "placeholder": "请输入责任销售姓名", "section": "项目基本信息"},
        {"id": "pf_3", "type": "text", "label": "项目编号", "key": "project_code", "required": False, "placeholder": "选填", "section": "项目基本信息"},
        {"id": "pf_4", "type": "select", "label": "项目类型", "key": "project_type", "required": True, "options": ["信息化", "智能化", "机电消防", "软件开放", "系统运维", "XC/SM", "军队武警", "其他"], "section": "项目基本信息"},
        {"id": "pf_5", "type": "number", "label": "预计金额", "key": "expected_amount", "required": True, "placeholder": "0.00", "unit": "万元", "section": "项目基本信息"},
        {"id": "pf_6", "type": "date", "label": "招标时间", "key": "tender_time", "required": False, "section": "项目基本信息"},
        {"id": "pf_7", "type": "date", "label": "投标时间", "key": "bid_time", "required": False, "section": "项目基本信息"},
        {"id": "pf_8", "type": "text", "label": "业主联系人", "key": "owner_contact_person", "required": False, "placeholder": "选填", "section": "项目基本信息"},
        {"id": "pf_9", "type": "text", "label": "业主联系方式", "key": "owner_contact_info", "required": False, "placeholder": "选填", "section": "项目基本信息"},

        # — 区域 2: 合作基本情况 —
        {"id": "pf_10", "type": "text", "label": "公司名称", "key": "partner_company", "required": True, "placeholder": "请输入公司名称", "section": "合作基本情况"},
        {"id": "pf_11", "type": "text", "label": "公司地址", "key": "company_address", "required": False, "placeholder": "选填", "section": "合作基本情况"},
        {"id": "pf_12", "type": "text", "label": "主要资质", "key": "main_qualification", "required": False, "placeholder": "选填", "section": "合作基本情况"},
        {"id": "pf_13", "type": "text", "label": "法定代表", "key": "legal_representative", "required": False, "placeholder": "选填", "section": "合作基本情况"},
        {"id": "pf_14", "type": "text", "label": "联系人", "key": "contact_person", "required": True, "placeholder": "请输入联系人", "section": "合作基本情况"},
        {"id": "pf_15", "type": "text", "label": "联系方式", "key": "contact_info", "required": True, "placeholder": "请输入联系方式", "section": "合作基本情况"},
        {"id": "pf_16", "type": "select", "label": "合作模式", "key": "cooperation_mode", "required": False, "options": ["长期合作", "短期合作"], "section": "合作基本情况"},
        {"id": "pf_17", "type": "select", "label": "费用模式", "key": "fee_mode", "required": False, "options": ["互免", "收费"], "section": "合作基本情况"},
        {"id": "pf_18", "type": "number", "label": "费用金额", "key": "fee_amount", "required": False, "placeholder": "0.00", "unit": "元", "section": "合作基本情况"},
        {"id": "pf_19", "type": "select", "label": "中标状态", "key": "win_bid_status", "required": False, "options": ["进行中", "中标", "未中标"], "section": "合作基本情况"},
        {"id": "pf_20", "type": "select", "label": "是否SM", "key": "is_sm", "required": False, "options": ["是", "否"], "section": "合作基本情况"},

        # — 区域 3: 项目基本情况 —
        {"id": "pf_21", "type": "textarea", "label": "项目基本情况", "key": "project_overview", "required": False, "placeholder": "选填", "section": "项目基本情况"},

        # — 区域 4: 文件管理 —
        {"id": "pf_22", "type": "file", "label": "招标资料", "key": "tender_file", "required": False, "accept": ".pdf,.doc,.docx,.xls,.xlsx", "multiple": True, "section": "文件管理"},
        {"id": "pf_23", "type": "file", "label": "投标文档", "key": "bid_file", "required": False, "accept": ".pdf,.doc,.docx,.xls,.xlsx", "multiple": True, "section": "文件管理"},
    ]

    update_data = {
        "name": "自建项目登记表",
        "description": "自建项目登记表单，文件存储在 NAS 独立目录（自建项目/）",
        "fields": new_fields,
        "storage_sub_path": "自建项目",
    }

    # 更新模板 ID=2
    r = requests.put(f'{BASE}/forms/templates/2', json=update_data, headers=headers, proxies=PROXIES)
    if r.status_code == 200:
        result = r.json()
        print(f"✅ 模板更新成功: {result['name']}")
        print(f"   storage_sub_path: {result.get('storage_sub_path')}")
        print(f"   字段数量: {len(result.get('fields', []))}")
        for f in result.get('fields', []):
            section = f.get('section', '无分区')
            print(f"   - [{section}] {f['label']} ({f['type']})")
    else:
        print(f"❌ 更新失败: {r.status_code}")
        print(r.text[:500])

if __name__ == '__main__':
    main()
