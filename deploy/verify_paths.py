"""验证自建项目 vs 渠道项目的 NAS 路径分离"""
import requests
import json

BASE = 'http://127.0.0.1:8765/api'
PROXIES = {'http': None, 'https': None}

def main():
    # 登录
    r = requests.post(f'{BASE}/auth/login', data={'username': 'admin', 'password': 'akwj210627'}, proxies=PROXIES)
    token = r.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 获取所有模板
    r = requests.get(f'{BASE}/forms/templates', headers=headers, proxies=PROXIES)
    templates = r.json()

    for tpl in templates:
        print(f'\n=== 模板: {tpl["name"]} (ID={tpl["id"]}) ===')
        print(f'  storage_sub_path: {tpl.get("storage_sub_path")}')

        # 创建实例
        r = requests.post(f'{BASE}/forms/instances', json={
            'template_id': tpl['id'],
            'data': {'project_name': f'测试_{tpl["name"]}', 'responsible_sales': '张三'}
        }, headers=headers, proxies=PROXIES)
        instance_id = r.json()['id']

        # 初始化目录
        r = requests.post(f'{BASE}/forms/file-storage/init-folders', json={
            'instance_id': instance_id,
            'template_id': tpl['id'],
            'project_name': f'测试_{tpl["name"]}'
        }, headers=headers, proxies=PROXIES)
        result = r.json()
        print(f'  招标资料路径: {result.get("tender_folder", "N/A")}')
        print(f'  投标文档路径: {result.get("bid_folder", "N/A")}')

        # 验证路径包含 storage_sub_path
        expected = tpl.get('storage_sub_path') or tpl['name']
        tender_path = result.get('tender_folder', '')
        if expected in tender_path:
            print(f'  ✅ 路径包含 "{expected}" — 存储隔离正常')
        else:
            print(f'  ⚠️ 路径未包含 "{expected}"')

    print('\n=== 验证完成 ===')
    print('自建项目模板路径应包含 "自建项目"')
    print('其他模板路径应包含各自的 storage_sub_path 或模板名称')

if __name__ == '__main__':
    main()
