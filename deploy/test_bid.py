"""测试 admin 修改 win_bid_status"""
import requests

BASE = 'http://127.0.0.1:8000'
r = requests.post(f'{BASE}/api/auth/login',
                  data={'username': 'admin', 'password': 'akwj210627'},
                  headers={'Content-Type': 'application/x-www-form-urlencoded'})
print('login:', r.status_code, 'OK' if r.status_code == 200 else r.json().get('detail'))
if r.status_code != 200:
    raise SystemExit(1)
token = r.json()['access_token']
h = {'Authorization': 'Bearer ' + token}

# 获取项目列表
r2 = requests.get(f'{BASE}/api/projects?page=1&page_size=5', headers=h)
print('list:', r2.status_code, 'count:', len(r2.json().get('items', [])))
items = r2.json().get('items', [])
if not items:
    print('no items')
    raise SystemExit(1)

pid = items[0]['id']
old_status = items[0].get('win_bid_status')
print(f'Project id={pid}, win_bid_status={old_status}')

# 修改
r3 = requests.put(f'{BASE}/api/projects/{pid}',
                  json={'win_bid_status': 'yes'},
                  headers=h)
print(f'PUT status: {r3.status_code}')
print(f'PUT body: {r3.text[:500]}')

# 重新查
r4 = requests.get(f'{BASE}/api/projects/{pid}', headers=h)
new_status = r4.json().get('win_bid_status') if r4.status_code == 200 else 'ERR'
print(f'After PUT: win_bid_status={new_status}')
print(f'Changed? {old_status != new_status}')