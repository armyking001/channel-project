"""测试 win_bid_status 锁定后不能再改"""
import requests

BASE = 'http://127.0.0.1:8000'

# admin 登录
r = requests.post(f'{BASE}/api/auth/login',
                  data={'username': 'admin', 'password': 'akwj210627'},
                  headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = r.json()['access_token']
h = {'Authorization': 'Bearer ' + token}

# 找刚测过的项目 (id=4)
r = requests.get(f'{BASE}/api/projects/4', headers=h)
print('Project 4:', r.json().get('win_bid_status'), 'locked at:', r.json().get('win_bid_status_set_at'))

# 试着改回 'in_progress'
print('\nTry change win_bid_status: yes -> in_progress...')
r = requests.put(f'{BASE}/api/projects/4',
                 json={'win_bid_status': 'in_progress'},
                 headers=h)
print(f'  status: {r.status_code}')
print(f'  body: {r.text[:200]}')

# 试着改成 'no'
print('\nTry change win_bid_status: yes -> no...')
r = requests.put(f'{BASE}/api/projects/4',
                 json={'win_bid_status': 'no'},
                 headers=h)
print(f'  status: {r.status_code}')
print(f'  body: {r.text[:200]}')

# 再查状态
r = requests.get(f'{BASE}/api/projects/4', headers=h)
print(f'\nFinal: win_bid_status={r.json().get("win_bid_status")} (should still be "yes")')