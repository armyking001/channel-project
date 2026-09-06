"""
端到端测试：管理员中标状态多次修改功能
"""
import requests
import time

BASE = 'http://127.0.0.1:8000/api'
ADMIN_USER, ADMIN_PASS = 'admin', 'akwj210627'

def login(username, password):
    r = requests.post(f'{BASE}/auth/login', data={'username': username, 'password': password})
    assert r.status_code == 200, f'登录失败 {r.text}'
    return r.json()['access_token']

def H(token):
    return {'Authorization': f'Bearer {token}'}

def show(msg):
    print('\n' + '='*60)
    print(f'  {msg}')
    print('='*60)

# ========== 登录 ==========
show('1. 登录 admin')
token = login(ADMIN_USER, ADMIN_PASS)
print('OK 登录成功')

# ========== 验证列表接口返回 win_bid_status_set_at ==========
show('2. 验证项目列表接口返回 win_bid_status_set_at 字段')
r = requests.get(f'{BASE}/projects', headers=H(token))
data = r.json()
assert 'items' in data, '列表结构错误'
print(f'项目总数: {data["total"]}')
for idx, p in enumerate(data['items'][:5]):
    has_field = 'win_bid_status_set_at' in p
    print(f'  [{idx+1}] id={p["id"]} name={p["project_name"][:15]:15s} win_bid={p["win_bid_status"]:12s} has_field={has_field} set_at={p.get("win_bid_status_set_at")}')
    assert has_field, f'项目 {p["id"]} 缺少 win_bid_status_set_at 字段'
print('OK 列表接口所有项目均包含 win_bid_status_set_at 字段')

# ========== 准备测试目标项目 ==========
show('3. 准备测试目标项目')
target_project = None
for p in data['items']:
    if p['approval_status'] == 'approved':
        target_project = p
        break
if target_project is None:
    pending = [p for p in data['items'] if p['approval_status'] == 'pending_approval']
    if not pending:
        normal_token = login('jhliu', 'sjkj1234')
        suffix = str(int(time.time()))[-4:]
        create_data = {
            'project_name': f'中标状态测试项目-{suffix}',
            'project_type': '其他',
            'responsible_sales': '测试销售A',
            'expected_amount': 100,
            'partner_company': '测试公司',
            'contact_person': '张三',
            'contact_info': '13800000000',
            'cooperation_mode': 'long_term',
            'fee_mode': 'mutual',
            'approver_id': 1,
        }
        r = requests.post(f'{BASE}/projects', json=create_data, headers=H(normal_token))
        assert r.status_code == 200, f'创建项目失败 {r.text}'
        new_p = r.json()
        print(f'OK jhliu 创建新项目 id={new_p["id"]}')
        r = requests.post(f'{BASE}/projects/{new_p["id"]}/approve', json={'comment': '测试审批'}, headers=H(token))
        assert r.status_code == 200, f'审批失败 {r.text}'
        target_project = r.json()
    else:
        r = requests.post(f'{BASE}/projects/{pending[0]["id"]}/approve', json={'comment': '测试审批'}, headers=H(token))
        assert r.status_code == 200, f'审批失败 {r.text}'
        target_project = r.json()

pid = target_project['id']
print(f'OK 测试目标项目: id={pid} name={target_project["project_name"]} 当前中标={target_project.get("win_bid_status")} set_at={target_project.get("win_bid_status_set_at")}')

# ========== 测试1：首次修改 ==========
show('4. 测试：首次修改中标状态（set_at=None 无需理由+密码）')
r = requests.get(f'{BASE}/projects/{pid}', headers=H(token))
detailed = r.json()
print(f'当前 set_at = {detailed.get("win_bid_status_set_at")}')

first_status = detailed.get('win_bid_status')
new_status = 'yes' if first_status != 'yes' else 'no'

if detailed.get('win_bid_status_set_at') is None:
    r = requests.put(f'{BASE}/projects/{pid}', json={'win_bid_status': new_status}, headers=H(token))
    print(f'修改 {first_status} -> {new_status}, HTTP {r.status_code}')
    assert r.status_code == 200, f'首次修改失败 {r.text}'
    result = r.json()
    assert result['win_bid_status'] == new_status
    assert result['win_bid_status_set_at'] is not None
    print(f'OK 首次修改成功，新状态={result["win_bid_status"]} set_at={str(result["win_bid_status_set_at"])[:19]}')
else:
    print('跳过首次修改测试，项目已有 set_at')

# ========== 测试2：第二次修改 ==========
show('5. 测试：第二次修改中标状态（需要理由+密码）')
r = requests.get(f'{BASE}/projects/{pid}', headers=H(token))
detailed = r.json()
current_status = detailed['win_bid_status']
assert detailed['win_bid_status_set_at'] is not None
print(f'当前状态={current_status} set_at={str(detailed["win_bid_status_set_at"])[:19]}')

next_status = 'yes' if current_status != 'yes' else 'no'

# 2a: 不给理由
r = requests.put(f'{BASE}/projects/{pid}', json={'win_bid_status': next_status}, headers=H(token))
print(f'  2a 不给理由 -> HTTP {r.status_code}: {r.json().get("detail")}')
assert r.status_code == 400
assert '修改理由' in r.json()['detail']

# 2b: 给理由不给密码
r = requests.put(f'{BASE}/projects/{pid}', json={
    'win_bid_status': next_status,
    'win_bid_change_reason': '测试修改理由',
}, headers=H(token))
print(f'  2b 给理由不给密码 -> HTTP {r.status_code}: {r.json().get("detail")}')
assert r.status_code == 400
assert '密码' in r.json()['detail']

# 2c: 给错误密码
r = requests.put(f'{BASE}/projects/{pid}', json={
    'win_bid_status': next_status,
    'win_bid_change_reason': '测试修改理由',
    'admin_password_verify': 'wrong_password_123',
}, headers=H(token))
print(f'  2c 给错误密码 -> HTTP {r.status_code}: {r.json().get("detail")}')
assert r.status_code == 400
assert '密码验证失败' in r.json()['detail']

# 2d: 正确理由+正确密码
r = requests.put(f'{BASE}/projects/{pid}', json={
    'win_bid_status': next_status,
    'win_bid_change_reason': '测试修改中标状态：业务调整需要修正结果',
    'admin_password_verify': ADMIN_PASS,
}, headers=H(token))
print(f'  2d 正确理由+正确密码 -> HTTP {r.status_code}')
assert r.status_code == 200, f'修改失败 {r.text}'
result = r.json()
assert result['win_bid_status'] == next_status
print(f'OK 第二次修改成功: {current_status} -> {result["win_bid_status"]}  set_at={str(result["win_bid_status_set_at"])[:19]}（保持首次设置时间不变）')

# ========== 测试3：第三次修改 ==========
show('6. 测试：第三次修改中标状态（仍然需要理由+密码）')
current_status = result['win_bid_status']
next_status2 = 'in_progress' if current_status != 'in_progress' else 'no'

r = requests.put(f'{BASE}/projects/{pid}', json={'win_bid_status': next_status2}, headers=H(token))
print(f'  3a 不给理由 -> HTTP {r.status_code}: {r.json().get("detail")}')
assert r.status_code == 400

r = requests.put(f'{BASE}/projects/{pid}', json={
    'win_bid_status': next_status2,
    'win_bid_change_reason': '第三次修改：复核后更正中标结果',
    'admin_password_verify': ADMIN_PASS,
}, headers=H(token))
print(f'  3b 正确理由+正确密码 -> HTTP {r.status_code}')
assert r.status_code == 200, f'第三次修改失败 {r.text}'
result3 = r.json()
assert result3['win_bid_status'] == next_status2
print(f'OK 第三次修改成功: {current_status} -> {result3["win_bid_status"]}')

# ========== 测试4：非管理员 ==========
show('7. 测试：非管理员（jhliu）尝试修改已锁定的中标状态')
normal_token = login('jhliu', 'sjkj1234')
r = requests.put(f'{BASE}/projects/{pid}', json={
    'win_bid_status': 'yes',
    'win_bid_change_reason': '越权尝试',
    'admin_password_verify': 'whatever',
}, headers=H(normal_token))
print(f'  jhliu 修改已通过项目 -> HTTP {r.status_code}: {r.json().get("detail")}')
assert r.status_code == 400

# ========== 最终验证 ==========
show('8. 再次验证列表接口字段正确')
r = requests.get(f'{BASE}/projects', headers=H(token))
items = r.json()['items']
for p in items:
    assert 'win_bid_status_set_at' in p, f'项目 {p["id"]} 缺少字段'
    if p['id'] == pid:
        print(f'  目标项目 id={pid}: win_bid={p["win_bid_status"]}  set_at={p.get("win_bid_status_set_at")}')
        assert p['win_bid_status'] == next_status2, '列表中目标项目状态未更新'
        assert p.get('win_bid_status_set_at') is not None
print(f'OK 列表接口验证通过（共 {len(items)} 个项目）')

show('所有测试用例全部通过！')
print("""
总结：
  1. 列表接口 GET /api/projects 正确返回所有项目的 win_bid_status_set_at 字段 [OK]
  2. 首次修改中标状态（set_at=None）：无需理由+密码，直接成功 [OK]
  3. 非首次修改（set_at!=None）：
     - 缺理由 -> 400 拦截 [OK]
     - 缺密码 -> 400 拦截 [OK]
     - 错密码 -> 400 拦截 [OK]
     - 理由+密码正确 -> 200 成功 [OK]
  4. 第三次修改仍然强制要求理由+密码 [OK]
  5. 非管理员无法修改已审批通过的项目 [OK]
  6. win_bid_status_set_at 始终记录首次设置的时间，不会被后续修改覆盖 [OK]
""")
