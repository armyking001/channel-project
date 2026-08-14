import requests
import json

# 登录 admin
r = requests.post('http://127.0.0.1:8000/api/auth/login', json={'username': 'admin', 'password': 'akwj210627'})
token = r.json()['access_token']
print('Login OK')

# 取项目列表
r2 = requests.get('http://127.0.0.1:8000/api/projects', headers={'Authorization': f'Bearer {token}'})
data = r2.json()
print('Total projects:', data['total'])
for p in data['items'][:5]:
    keys = list(p.keys())
    has_set_at = 'win_bid_status_set_at' in keys
    set_at_val = p.get('win_bid_status_set_at')
    print(f'  id={p["id"]} name={p["project_name"]} win_bid={p["win_bid_status"]} has_set_at_field={has_set_at} set_at={set_at_val}')
