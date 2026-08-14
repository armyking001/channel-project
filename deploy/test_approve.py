"""直接调用服务器 API 测试审批"""
import requests
# admin 登录
r = requests.post('http://172.16.10.92:26731/api/auth/login',
                  data={'username': 'jhliu', 'password': 'sjq1234'})
print('Login:', r.status_code, r.json().get('detail') or 'OK')
if r.status_code != 200:
    r = requests.post('http://172.16.10.92:26731/api/auth/login',
                      data={'username': 'jhliu', 'password': 'jhliu123'})
    print('Retry:', r.status_code, r.json().get('detail') or 'OK')

if r.status_code == 200:
    token = r.json()['access_token']
    # 找待审批的项目
    h = {'Authorization': 'Bearer ' + token}
    r2 = requests.get('http://172.16.10.92:26731/api/projects?approval_status=pending_approval',
                       headers=h)
    print('Pending:', r2.status_code)
    if r2.status_code == 200:
        data = r2.json()
        items = data.get('items', data) if isinstance(data, dict) else data
        if items and len(items) > 0:
            pid = items[0]['id']
            print('Will approve project:', pid, items[0].get('project_name'))
            # 测试通过接口
            r3 = requests.post(f'http://172.16.10.92:26731/api/approvals/{pid}/approve', headers=h)
            print('Approve result:', r3.status_code, r3.json())
        else:
            print('No pending projects')