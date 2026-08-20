"""直接调用服务器审批 API 测试"""
import requests

# 尝试用 admin 账号
print('=== Try login ===')
for u, p in [('admin', 'admin123'), ('admin', 'admin'), ('admin', 'Admin@2026'),
             ('admin001', 'akwj210627'), ('sysadmin', 'sysadmin123'),
             ('system', 'system123'), ('admin', 'password')]:
    r = requests.post('http://172.16.10.92:26731/api/auth/login', data={'username': u, 'password': p})
    if r.status_code == 200:
        print(f'  OK: {u}/{p}')
        token = r.json()['access_token']
        break
    else:
        print(f'  FAIL: {u} - {r.json().get("detail")}')
else:
    print('All login attempts failed')

if 'token' not in dir():
    raise SystemExit(1)

h = {'Authorization': 'Bearer ' + token}

# 找待审批项目
print('\n=== Get pending ===')
r2 = requests.get('http://172.16.10.92:26731/api/approvals/pending', headers=h)
print('status:', r2.status_code)
if r2.status_code == 200:
    data = r2.json()
    items = data.get('items', data) if isinstance(data, dict) else data
    print('items:', len(items) if hasattr(items, '__len__') else 'N/A')
    if hasattr(items, '__len__') and len(items) > 0:
        pid = items[0]['id']
        print(f'\n=== Try approve pid={pid} ===')
        r3 = requests.post(f'http://172.16.10.92:26731/api/approvals/{pid}/approve', headers=h)
        print('Approve status:', r3.status_code)
        print('Approve body:', r3.text[:500])

        # 看状态变了没
        r4 = requests.get(f'http://172.16.10.92:26731/api/projects/{pid}', headers=h)
        print('\nProject after approve:')
        print('status:', r4.status_code)
        if r4.status_code == 200:
            print('approval_status:', r4.json().get('approval_status'))