"""端到端测试：jhliu 建项目 → admin 审批 → admin 修改中标状态"""
import requests
import time

BASE = 'http://127.0.0.1:8000'


def login(username, password):
    r = requests.post(f'{BASE}/api/auth/login',
                      data={'username': username, 'password': password},
                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if r.status_code != 200:
        print(f'  ❌ login {username}: {r.status_code} {r.text[:200]}')
        return None
    print(f'  ✅ login {username} OK ({r.json()["user"]["role"]})')
    return r.json()['access_token']


def h(token):
    return {'Authorization': 'Bearer ' + token}


# ============ Step 1: jhliu 登录并创建项目 ============
print('=' * 60)
print('Step 1: jhliu (普通账号) 创建项目')
print('=' * 60)
jhliu_token = login('jhliu', 'sjkj1234')
if not jhliu_token:
    raise SystemExit(1)

# 找 jhliu 的审批人（看 jluo 是上级，应该是审批人）
r = requests.get(f'{BASE}/api/users', headers=h(jhliu_token))
print(f'  users list: {r.status_code}')
items = r.json() if r.status_code == 200 else []
if isinstance(items, dict):
    items = items.get('items', [])
approvers = [u for u in items if u.get('role') in ('admin', 'important') and u.get('is_active')]
print(f'  available approvers: {[(u["real_name"], u["role"]) for u in approvers]}')

# 找一个 approver
admin_user = next((u for u in items if u['username'] == 'admin'), None)
if not admin_user:
    print('  ❌ no admin user')
    raise SystemExit(1)
approver_id = admin_user['id']
print(f'  → use approver: {admin_user["real_name"]} (id={approver_id})')

# 创建项目
project_data = {
    'project_name': f'测试项目_{int(time.time())}',
    'project_type': '信息化',
    'responsible_sales': '测试人A',
    'partner_company': '测试合作单位',
    'contact_person': '张经理',
    'contact_info': '13800001111',
    'cooperation_mode': 'long_term',
    'fee_mode': 'mutual',
    'is_sm': 'no',
    'expected_amount': '100',
    'project_amount': 1000000,
    'main_qualification': '无',
    'legal_representative': '王总',
    'approver_id': approver_id,
}
r = requests.post(f'{BASE}/api/projects', json=project_data, headers=h(jhliu_token))
print(f'  create status: {r.status_code}')
if r.status_code != 200:
    print(f'  ❌ body: {r.text[:500]}')
    raise SystemExit(1)
project = r.json()
pid = project['id']
print(f'  ✅ created project id={pid}, status={project["approval_status"]}')
print(f'     name: {project["project_name"]}')

# ============ Step 2: 提交审批 ============
print()
print('=' * 60)
print('Step 2: jhliu 提交审批')
print('=' * 60)
r = requests.post(f'{BASE}/api/projects/{pid}/submit', headers=h(jhliu_token))
print(f'  submit status: {r.status_code}, body: {r.text[:200]}')

# ============ Step 3: admin 登录并审批通过 ============
print()
print('=' * 60)
print('Step 3: admin (系统管理员) 审批通过')
print('=' * 60)
admin_token = login('admin', 'akwj210627')
if not admin_token:
    raise SystemExit(1)

# 查 admin 待审批列表
r = requests.get(f'{BASE}/api/approvals/pending', headers=h(admin_token))
print(f'  pending list status: {r.status_code}')
pending_data = r.json() if r.status_code == 200 else {}
pending_items = pending_data.get('items', [])
print(f'  pending count: {len(pending_items)}')

# 审批通过
r = requests.post(f'{BASE}/api/approvals/{pid}/approve', headers=h(admin_token))
print(f'  approve status: {r.status_code}, body: {r.text[:200]}')

# 验证状态
r = requests.get(f'{BASE}/api/projects/{pid}', headers=h(admin_token))
if r.status_code == 200:
    p = r.json()
    print(f'  ✅ project status after approve: {p["approval_status"]}')

# ============ Step 4: admin 修改中标状态 ============
print()
print('=' * 60)
print('Step 4: admin 修改中标状态为"中标"')
print('=' * 60)
r = requests.put(f'{BASE}/api/projects/{pid}',
                 json={'win_bid_status': 'yes'},
                 headers=h(admin_token))
print(f'  PUT status: {r.status_code}')
if r.status_code != 200:
    print(f'  ❌ body: {r.text[:500]}')
else:
    print(f'  ✅ saved')

# 验证
r = requests.get(f'{BASE}/api/projects/{pid}', headers=h(admin_token))
if r.status_code == 200:
    p = r.json()
    print(f'  ✅ final win_bid_status: {p["win_bid_status"]}')

print()
print('=' * 60)
print('🎉 全部测试通过！')
print('=' * 60)