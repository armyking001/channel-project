"""检查测试813项目的状态"""
import requests
r = requests.post('http://127.0.0.1:8000/api/auth/login', data={'username':'admin','password':'akwj210627'}, headers={'Content-Type':'application/x-www-form-urlencoded'})
token = r.json()['access_token']
h = {'Authorization': 'Bearer ' + token}

r = requests.get('http://127.0.0.1:8000/api/projects?page=1&page_size=50', headers=h)
items = r.json()['items']
target = next((p for p in items if '测试813' in p['project_name']), None)
if not target:
    print('not found')
else:
    pid = target['id']
    print(f'Project id={pid}')
    print(f'  win_bid_status={target["win_bid_status"]}')
    print(f'  win_bid_status_set_at={target.get("win_bid_status_set_at")}')
    # 试着改
    print('\nTry PUT win_bid_status=yes...')
    r2 = requests.put(f'http://127.0.0.1:8000/api/projects/{pid}', json={'win_bid_status': 'yes'}, headers=h)
    print(f'  PUT status: {r2.status_code}')
    print(f'  body: {r2.text[:300]}')
    # 再查
    r3 = requests.get(f'http://127.0.0.1:8000/api/projects/{pid}', headers=h)
    print(f'  After: win_bid_status={r3.json().get("win_bid_status")}')
    print(f'  set_at: {r3.json().get("win_bid_status_set_at")}')