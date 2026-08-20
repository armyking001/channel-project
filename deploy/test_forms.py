"""测试表单生成器 API"""
import requests

BASE = 'http://127.0.0.1:9800'

# 登录
r = requests.post(f'{BASE}/api/auth/login', data={'username': 'admin', 'password': 'akwj210627'})
print('Login:', r.status_code)
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 测试表单模板列表
r2 = requests.get(f'{BASE}/api/forms/templates', headers=headers)
print('GET /forms/templates:', r2.status_code, r2.json())

# 创建测试表单模板
r3 = requests.post(f'{BASE}/api/forms/templates', json={
    'name': '合同登记表',
    'description': '用于登记合同信息',
    'fields': [
        {'id': 'f1', 'type': 'text', 'label': '合同名称', 'key': 'contract_name', 'required': True, 'placeholder': '请输入合同名称'},
        {'id': 'f2', 'type': 'number', 'label': '合同金额', 'key': 'amount', 'required': True, 'unit': '万元', 'placeholder': '请输入金额'},
        {'id': 'f3', 'type': 'date', 'label': '签订日期', 'key': 'sign_date', 'required': True},
        {'id': 'f4', 'type': 'select', 'label': '合同类型', 'key': 'contract_type', 'required': False, 'options': ['采购', '服务', '工程', '其他']},
    ]
}, headers=headers)
print('POST /forms/templates:', r3.status_code)
if r3.status_code == 200:
    tpl = r3.json()
    print('  id:', tpl['id'], 'name:', tpl['name'], 'fields:', len(tpl['fields']))

    # 提交表单实例
    r4 = requests.post(f'{BASE}/api/forms/instances', json={
        'template_id': tpl['id'],
        'data': {'contract_name': '测试合同', 'amount': 100, 'sign_date': '2026-08-14', 'contract_type': '采购'}
    }, headers=headers)
    print('POST /forms/instances:', r4.status_code)
    if r4.status_code == 200:
        print('  id:', r4.json()['id'], 'data:', r4.json()['data'])

    # 查询实例列表
    tid = tpl['id']
    r5 = requests.get(f'{BASE}/api/forms/instances?template_id={tid}', headers=headers)
    print('GET /forms/instances:', r5.status_code, 'total:', r5.json()['total'])

    # 删除测试模板
    r6 = requests.delete(f'{BASE}/api/forms/templates/{tid}', headers=headers)
    print('DELETE /forms/templates:', r6.status_code)
else:
    print('Error:', r3.text[:500])
