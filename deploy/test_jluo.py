"""Test 审批通过/驳回 - 使用 jluo 账号登录"""
import requests
import sys

BASE = 'http://172.16.10.92:26731'

# 1. 登录
print('[1] Login as jluo...')
r = requests.post(f'{BASE}/api/auth/login', data={'username': 'jluo', 'password': 'sjkj1234'})
print(f'  status: {r.status_code}')
if r.status_code != 200:
    print(f'  FAIL: {r.text[:300]}')
    sys.exit(1)
token = r.json()['access_token']
print(f'  OK, role: {r.json().get("role")}, real_name: {r.json().get("real_name")}')

h = {'Authorization': 'Bearer ' + token}

# 2. 找待审批项目
print('\n[2] Get pending projects...')
r2 = requests.get(f'{BASE}/api/approvals/pending', headers=h)
print(f'  status: {r2.status_code}')
if r2.status_code != 200:
    print(f'  FAIL: {r2.text[:300]}')
    sys.exit(1)
data = r2.json()
items = data.get('items', data) if isinstance(data, dict) else data
print(f'  count: {len(items)}')
if not items:
    print('  No pending projects')
    sys.exit(0)

# 打印所有待审批项目
for i, p in enumerate(items, 1):
    print(f'    {i}. id={p["id"]}  name={p.get("project_name")}  status={p.get("approval_status")}')

# 3. 审批通过项目 1，驳回项目 2
target_pass = items[0]
target_reject = items[1] if len(items) >= 2 else None

if target_pass:
    print(f'\n[3a] Approve project id={target_pass["id"]} ({target_pass.get("project_name")})...')
    r3 = requests.post(f'{BASE}/api/approvals/{target_pass["id"]}/approve', headers=h)
    print(f'  status: {r3.status_code}')
    print(f'  body: {r3.text[:300]}')

if target_reject:
    print(f'\n[3b] Reject project id={target_reject["id"]} ({target_reject.get("project_name")})...')
    r4 = requests.post(f'{BASE}/api/approvals/{target_reject["id"]}/reject', headers=h)
    print(f'  status: {r4.status_code}')
    print(f'  body: {r4.text[:300]}')

# 4. 验证状态
print('\n[4] Verify state after...')
for p in items[:2]:
    pid = p['id']
    r5 = requests.get(f'{BASE}/api/projects/{pid}', headers=h)
    if r5.status_code == 200:
        d = r5.json()
        print(f'  id={pid} name={d.get("project_name")} status={d.get("approval_status")}')
    else:
        print(f'  id={pid} GET failed: {r5.status_code}')

# 5. 看"我已审批"
print('\n[5] History list...')
r6 = requests.get(f'{BASE}/api/approvals/history', headers=h)
if r6.status_code == 200:
    data2 = r6.json()
    items2 = data2.get('items', [])
    print(f'  history count: {len(items2)}')
    for p in items2[:3]:
        print(f'    id={p["id"]} name={p.get("project_name")} status={p.get("approval_status")}')