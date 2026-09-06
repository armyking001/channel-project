"""
审批流程权限测试脚本
====================
测试目标：
1. 普通用户创建项目后，审批人能在"待我审批"列表中看到
2. 只有指定审批人才能审批项目（通过/驳回）
3. admin 可以审批任何项目
4. 非审批人（包括其他 important 角色）不能审批
5. 审批后项目状态正确流转
6. 项目列表权限控制正确

使用方法：
    python test_approval_permission.py

前置条件：
    1. 后端服务已启动（http://127.0.0.1:8000）
    2. 数据库中存在 admin 账号（默认密码：admin123）
    3. 数据库中存在至少一个 normal 角色用户
    4. 数据库中存在至少一个 important 角色用户作为审批人
"""

import requests
import json
import sys
import time

BASE = "http://127.0.0.1:8000"

# 创建 session 并禁用环境代理
session = requests.Session()
session.trust_env = False

# 测试结果统计
test_results = []


def log_test(name, passed, detail=""):
    """记录测试结果"""
    status = "✓ PASS" if passed else "✗ FAIL"
    test_results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  {status} | {name}")
    if detail:
        print(f"         {detail}")


def login(username, password):
    """用户登录，返回 token"""
    r = session.post(f"{BASE}/api/auth/login", data={
        "username": username,
        "password": password
    }, timeout=10)
    if r.status_code == 200:
        return r.json().get("access_token")
    return None


def get_headers(token):
    """获取请求头"""
    return {"Authorization": f"Bearer {token}"}


# ========== 测试用例 ==========

print("=" * 70)
print("审批流程权限测试")
print("=" * 70)

# 1. 登录 admin 获取所有用户信息
print("\n【阶段 1】获取测试用户信息")
admin_token = login("admin", "admin123")
if not admin_token:
    print("✗ 登录 admin 失败，退出测试")
    sys.exit(1)

headers = get_headers(admin_token)

# 获取用户列表
r = session.get(f"{BASE}/api/users", headers=headers, timeout=10)
users = r.json()
print(f"  找到 {len(users)} 个用户")

# 筛选测试用户
normal_user = None
important_user = None

for u in users:
    if u["role"] == "normal" and u["is_active"]:
        normal_user = u
    if u["role"] in ("important", "important_admin") and u["is_active"]:
        important_user = u

print(f"  普通用户: {normal_user['username']} ({normal_user['real_name']}) id={normal_user['id']}")
print(f"  重要账号: {important_user['username']} ({important_user['real_name']}) id={important_user['id']}")

if not normal_user or not important_user:
    print("✗ 缺少测试用户，退出测试")
    sys.exit(1)

# 2. 用普通用户登录
print("\n【阶段 2】测试普通用户创建项目")
normal_token = login(normal_user["username"], "admin123")
if not normal_token:
    print(f"✗ 登录普通用户 {normal_user['username']} 失败")
    sys.exit(1)

normal_headers = get_headers(normal_token)

# 创建项目（指定审批人为 important_user）
project_data = {
    "project_name": f"权限测试项目_{int(time.time())}",
    "partner_company": "测试合作公司",
    "cooperation_mode": "long_term",
    "fee_mode": "mutual",
    "is_sm": "no",
    "project_type": "其他",
    "win_bid_status": "in_progress",
    "approver_id": important_user["id"],
    "expected_amount": 100000,
}

r = session.post(f"{BASE}/api/projects", json=project_data, headers=normal_headers, timeout=10)
log_test(
    "创建项目（指定审批人）",
    r.status_code == 200,
    f"status={r.status_code}"
)

if r.status_code != 200:
    print(f"  错误详情: {r.text[:200]}")
    sys.exit(1)

project_id = r.json()["id"]
project_status = r.json()["approval_status"]
print(f"  项目ID={project_id}, 状态={project_status}")

# 验证创建后状态为 pending_approval
log_test(
    "项目创建后状态为 pending_approval",
    project_status == "pending_approval",
    f"实际状态: {project_status}"
)

# 3. 用审批人登录，验证能在待审批列表看到项目
print("\n【阶段 3】审批人验证待审批列表")
important_token = login(important_user["username"], "admin123")
if not important_token:
    print(f"✗ 登录审批人 {important_user['username']} 失败")
    sys.exit(1)

important_headers = get_headers(important_token)

# 查询待审批列表
r = session.get(f"{BASE}/api/approvals/pending", headers=important_headers, timeout=10)
log_test(
    "审批人获取待审批列表",
    r.status_code == 200,
    f"status={r.status_code}"
)

pending_items = r.json().get("items", [])
pending_ids = [p["id"] for p in pending_items]
log_test(
    f"待审批列表包含项目 {project_id}",
    project_id in pending_ids,
    f"列表中的项目ID: {pending_ids}"
)

# 4. 测试非审批人不能审批
print("\n【阶段 4】权限控制测试 - 非审批人不能审批")

# 创建另一个 important 用户（如果存在）来测试非审批人权限
other_important = None
for u in users:
    if u["role"] in ("important", "important_admin") and u["id"] != important_user["id"] and u["is_active"]:
        other_important = u
        break

if other_important:
    print(f"  使用另一个重要账号 {other_important['username']} 测试非审批人权限")
    other_token = login(other_important["username"], "admin123")
    
    if other_token:
        other_headers = get_headers(other_token)
        
        # 尝试审批（应该返回 403）
        r = session.post(
            f"{BASE}/api/approvals/{project_id}/approve",
            headers=other_headers,
            timeout=10
        )
        log_test(
            "非审批人无法审批项目（approvals/approve）",
            r.status_code == 403,
            f"status={r.status_code}, response={r.text[:100]}"
        )
        
        # 尝试通过 projects/approve 审批
        r = session.post(
            f"{BASE}/api/projects/{project_id}/approve",
            json={"comment": "测试审批"},
            headers=other_headers,
            timeout=10
        )
        log_test(
            "非审批人无法审批项目（projects/approve）",
            r.status_code == 403,
            f"status={r.status_code}, response={r.text[:100]}"
        )

# 5. 测试 admin 可以审批任何项目
print("\n【阶段 5】权限控制测试 - admin 可以审批任何项目")

# admin 审批
r = session.post(
    f"{BASE}/api/approvals/{project_id}/approve",
    headers=headers,  # admin headers
    timeout=10
)
log_test(
    "admin 可以审批项目（approvals/approve）",
    r.status_code == 200,
    f"status={r.status_code}, response={r.text[:100]}"
)

# 验证项目状态变为 approved
r = session.get(f"{BASE}/api/projects/{project_id}", headers=normal_headers, timeout=10)
project = r.json()
log_test(
    "admin 审批后项目状态为 approved",
    project["approval_status"] == "approved",
    f"实际状态: {project['approval_status']}"
)

# 6. 创建第二个项目，测试指定审批人审批流程
print("\n【阶段 6】完整审批流程测试")

project_data2 = {
    "project_name": f"权限测试项目2_{int(time.time())}",
    "partner_company": "测试合作公司2",
    "cooperation_mode": "short_term",
    "fee_mode": "charged",
    "is_sm": "no",
    "project_type": "信息化",
    "win_bid_status": "in_progress",
    "approver_id": important_user["id"],
    "expected_amount": 50000,
}

r = session.post(f"{BASE}/api/projects", json=project_data2, headers=normal_headers, timeout=10)
project2_id = r.json()["id"]
print(f"  创建第二个项目: ID={project2_id}")

# 指定审批人审批通过
r = session.post(
    f"{BASE}/api/approvals/{project2_id}/approve",
    headers=important_headers,
    timeout=10
)
log_test(
    "指定审批人可以审批项目",
    r.status_code == 200,
    f"status={r.status_code}, response={r.text[:100]}"
)

# 验证项目状态
r = session.get(f"{BASE}/api/projects/{project2_id}", headers=normal_headers, timeout=10)
log_test(
    "指定审批人审批后项目状态为 approved",
    r.json()["approval_status"] == "approved",
    f"实际状态: {r.json()['approval_status']}"
)

# 7. 创建第三个项目，测试驳回流程
print("\n【阶段 7】驳回流程测试")

project_data3 = {
    "project_name": f"权限测试项目3_{int(time.time())}",
    "partner_company": "测试合作公司3",
    "cooperation_mode": "long_term",
    "fee_mode": "mutual",
    "is_sm": "no",
    "project_type": "软件开放",
    "win_bid_status": "in_progress",
    "approver_id": important_user["id"],
    "expected_amount": 30000,
}

r = session.post(f"{BASE}/api/projects", json=project_data3, headers=normal_headers, timeout=10)
project3_id = r.json()["id"]
print(f"  创建第三个项目: ID={project3_id}")

# 指定审批人驳回
r = session.post(
    f"{BASE}/api/approvals/{project3_id}/reject",
    headers=important_headers,
    timeout=10
)
log_test(
    "指定审批人可以驳回项目",
    r.status_code == 200,
    f"status={r.status_code}, response={r.text[:100]}"
)

# 验证项目状态为 rejected
r = session.get(f"{BASE}/api/projects/{project3_id}", headers=normal_headers, timeout=10)
log_test(
    "驳回后项目状态为 rejected",
    r.json()["approval_status"] == "rejected",
    f"实际状态: {r.json()['approval_status']}"
)

# 8. 测试审批人历史记录
print("\n【阶段 8】审批历史记录测试")

r = session.get(f"{BASE}/api/approvals/history", headers=important_headers, timeout=10)
log_test(
    "审批人获取已审批列表",
    r.status_code == 200,
    f"status={r.status_code}"
)

history_items = r.json().get("items", [])
history_ids = [p["id"] for p in history_items]
log_test(
    f"已审批列表包含项目 {project2_id}",
    project2_id in history_ids,
    f"已审批项目ID: {history_ids}"
)

log_test(
    f"已审批列表包含项目 {project3_id}",
    project3_id in history_ids,
    f"已审批项目ID: {history_ids}"
)

# 9. 测试项目列表权限控制
print("\n【阶段 9】项目列表权限控制测试")

# 普通用户只能看到自己的项目
r = session.get(f"{BASE}/api/projects", headers=normal_headers, timeout=10)
log_test(
    "普通用户获取项目列表",
    r.status_code == 200,
    f"status={r.status_code}"
)

user_projects = r.json().get("items", [])
for p in user_projects:
    log_test(
        f"普通用户项目列表中项目 {p['id']} 是自己创建的",
        p["created_by"] == normal_user["id"],
        f"created_by={p['created_by']}, 当前用户ID={normal_user['id']}"
    )

# 10. 测试审批摘要
print("\n【阶段 10】审批摘要接口测试")

r = session.get(f"{BASE}/api/approvals/summary", headers=important_headers, timeout=10)
log_test(
    "审批摘要接口正常",
    r.status_code == 200,
    f"status={r.status_code}, response={r.text[:200]}"
)

# ========== 清理测试数据 ==========
print("\n【清理】删除测试项目")

r = session.delete(f"{BASE}/api/projects/{project_id}", headers=normal_headers, timeout=10)
print(f"  删除项目1: status={r.status_code}")

r = session.delete(f"{BASE}/api/projects/{project2_id}", headers=normal_headers, timeout=10)
print(f"  删除项目2: status={r.status_code}")

r = session.delete(f"{BASE}/api/projects/{project3_id}", headers=normal_headers, timeout=10)
print(f"  删除项目3: status={r.status_code}")

# ========== 测试结果汇总 ==========
print("\n" + "=" * 70)
print("测试结果汇总")
print("=" * 70)

passed = sum(1 for t in test_results if t["passed"])
failed = sum(1 for t in test_results if not t["passed"])
total = len(test_results)

for i, t in enumerate(test_results, 1):
    status = "✓" if t["passed"] else "✗"
    print(f"  [{status}] {i}. {t['name']}")

print(f"\n总计: {total} 项测试，{passed} 项通过，{failed} 项失败")

if failed > 0:
    print("\n失败详情:")
    for t in test_results:
        if not t["passed"]:
            print(f"  ✗ {t['name']}: {t['detail']}")

print("=" * 70)

# 返回退出码
sys.exit(0 if failed == 0 else 1)