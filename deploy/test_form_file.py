"""测试表单文件存储 — 自建项目模板独立路径"""
import requests
import json
import os
import tempfile

BASE = 'http://127.0.0.1:8765/api'
PROXIES = {'http': None, 'https': None}

def main():
    # 1. 登录
    r = requests.post(f'{BASE}/auth/login', data={'username': 'admin', 'password': 'akwj210627'}, proxies=PROXIES)
    token = r.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. 获取模板
    r = requests.get(f'{BASE}/forms/templates', headers=headers, proxies=PROXIES)
    templates = r.json()
    tpl = next((t for t in templates if '自建项目' in t['name']), None)
    if not tpl:
        print('未找到自建项目模板，使用第一个模板测试')
        tpl = templates[0]
    print(f'使用模板: {tpl["id"]} - {tpl["name"]} (storage_sub_path={tpl.get("storage_sub_path")})')

    # 3. 创建表单实例
    r = requests.post(f'{BASE}/forms/instances', json={
        'template_id': tpl['id'],
        'data': {'project_name': '测试自建项目', 'responsible_sales': '张三', 'partner_company': '测试公司'}
    }, headers=headers, proxies=PROXIES)
    instance_id = r.json()['id']
    print(f'创建实例: id={instance_id}')

    # 4. 初始化目录
    r = requests.post(f'{BASE}/forms/file-storage/init-folders', json={
        'instance_id': instance_id,
        'template_id': tpl['id'],
        'project_name': '测试自建项目'
    }, headers=headers, proxies=PROXIES)
    print(f'初始化目录: {r.json()}')

    # 5. 创建临时文件并上传
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as f:
        f.write('测试内容 - 招标资料')
        tender_file = f.name
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as f:
        f.write('测试内容 - 投标文档')
        bid_file = f.name

    # 上传招标资料
    with open(tender_file, 'rb') as f:
        r = requests.post(f'{BASE}/forms/file-storage/upload', 
            data={'instance_id': instance_id, 'folder_type': 'tender'},
            files={'files': ('招标资料.txt', f)},
            headers=headers, proxies=PROXIES)
    print(f'上传招标资料: {r.json()}')

    # 上传投标文档
    with open(bid_file, 'rb') as f:
        r = requests.post(f'{BASE}/forms/file-storage/upload', 
            data={'instance_id': instance_id, 'folder_type': 'bid'},
            files={'files': ('投标文档.txt', f)},
            headers=headers, proxies=PROXIES)
    print(f'上传投标文档: {r.json()}')

    # 6. 列出文件
    r = requests.post(f'{BASE}/forms/file-storage/list-files', json={
        'instance_id': instance_id,
        'folder_type': 'tender'
    }, headers=headers, proxies=PROXIES)
    print(f'招标资料列表: {r.json()}')

    r = requests.post(f'{BASE}/forms/file-storage/list-files', json={
        'instance_id': instance_id,
        'folder_type': 'bid'
    }, headers=headers, proxies=PROXIES)
    print(f'投标文档列表: {r.json()}')

    # 7. 清理临时文件
    os.unlink(tender_file)
    os.unlink(bid_file)

    print('\n✅ 测试完成')

if __name__ == '__main__':
    main()
