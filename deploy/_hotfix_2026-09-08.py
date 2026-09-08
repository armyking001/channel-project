"""2026-09-08 hotfix: 通知管理持久化 + 审批金额对齐

仅上传 6 个变更文件,其他任何文件/服务/数据不动.
"""
import subprocess, os, sys, time
SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"
REMOTE_BASE = "/opt/channel-project"
LOCAL_BASE = r"Z:\soft-RED\hermes\开发软件\渠道项目登记"

def ssh(cmd, timeout=30):
    print(f"  ssh> {cmd[:80]}{'...' if len(cmd)>80 else ''}")
    r = subprocess.run(
        ["sshpass","-p",SSHPASS,"ssh","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10",
         f"{USER}@{SERVER}", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

def scp(src, dst, timeout=60):
    r = subprocess.run(
        ["sshpass","-p",SSHPASS,"scp","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10",
         src, f"{USER}@{SERVER}:{dst}"],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

def scp_via_tmp(src, remote_path, timeout=60):
    """scp 到 /tmp/ + sudo mv 到目标 (admin 无 static/ 写权限)"""
    name = remote_path.split('/')[-1]
    tmp_path = f"/tmp/{name}"
    rc, out, err = scp(src, tmp_path, timeout)
    if rc != 0:
        return rc, out, err
    rc, out, err = ssh(f"sudo mv {tmp_path} {remote_path} && sudo chown root:root {remote_path} 2>&1")
    return rc, out, err

print("=" * 60)
print("Hotfix 2026-09-08: 通知管理持久化 + 审批金额对齐")
print(f"目标服务器: {USER}@{SERVER}")
print("=" * 60)

print("\n=== [1/8] 服务器健康检查 ===")
rc, out, err = ssh("hostname; echo '---'; sudo -n systemctl is-active channel-project 2>&1; echo EXIT_$?")
print(f"  exit={rc}\n{out}")

print("\n=== [2/8] 备份 data.db ===")
rc, out, err = ssh(f"sudo cp {REMOTE_BASE}/backend/data.db {REMOTE_BASE}/data.db.bak.$(date +%Y%m%d_%H%M%S) && ls -la {REMOTE_BASE}/data.db.bak.* | tail -3")
print(f"  exit={rc}\n{out}")

print("\n=== [3/8] 停止服务 ===")
rc, out, err = ssh("sudo systemctl stop channel-project; sleep 1; sudo systemctl is-active channel-project 2>&1; echo STOP_EXIT_$?")
print(f"  exit={rc}\n{out}")

print("\n=== [4/8] SCP 上传 6 个文件 ===")
files = [
    ("backend/app/models.py", f"{REMOTE_BASE}/backend/app/models.py"),
    ("backend/app/routers/notifications_ws.py", f"{REMOTE_BASE}/backend/app/routers/notifications_ws.py"),
    ("backend/config.yaml", f"{REMOTE_BASE}/backend/config.yaml"),
    ("backend/static/index.html", f"{REMOTE_BASE}/backend/static/index.html"),
    ("backend/static/assets/index-D0_cB0gD.css", f"{REMOTE_BASE}/backend/static/assets/index-D0_cB0gD.css"),
    ("backend/static/assets/index-XZPlD_zl.js", f"{REMOTE_BASE}/backend/static/assets/index-XZPlD_zl.js"),
]
for rel, remote in files:
    local = os.path.join(LOCAL_BASE, rel).replace("\\","/")
    sz = os.path.getsize(local)
    # static 目录需要 sudo 走 /tmp 中转；其他目录直接 scp
    use_tmp = "/static/" in remote
    if use_tmp:
        print(f"  -> {rel} ({sz:,} bytes) [scp + sudo mv]")
        rc, out, err = scp_via_tmp(local, remote, timeout=120)
    else:
        print(f"  -> {rel} ({sz:,} bytes) [direct scp]")
        rc, out, err = scp(local, remote, timeout=120)
    if rc != 0:
        print(f"  ❌ FAIL rc={rc}")
        print(f"  stderr: {err.strip()}")
        sys.exit(1)
print("  ✅ 全部上传成功")

print("\n=== [5/8] 启动服务 ===")
rc, out, err = ssh("sudo systemctl start channel-project; sleep 5; sudo systemctl is-active channel-project; echo START_EXIT_$?")
print(f"  exit={rc}\n{out}")

print("\n=== [6/8] 健康检查 (重试) ===")
for i in range(8):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        break
    time.sleep(2)

print("\n=== [7/8] 验证新接口 ===")
# admin 登录
rc, out, err = ssh("curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin&password=akwj210627'")
print(f"  login exit={rc}")
print(f"  login response (first 200): {out[:200]}")
try:
    import json
    tok = json.loads(out)['access_token']
    print(f"  token: {tok[:50]}...")
    rc, out, err = ssh(f"curl -s http://127.0.0.1:8000/api/notifications/announce/draft -H 'Authorization: Bearer {tok}'")
    print(f"  GET /announce/draft -> {out[:200]}")
    rc, out, err = ssh(f"curl -s 'http://127.0.0.1:8000/api/notifications/announce/history?limit=3' -H 'Authorization: Bearer {tok}'")
    print(f"  GET /announce/history -> {out[:300]}")
except Exception as e:
    print(f"  ⚠️ 接口验证跳过: {e}")

print("\n=== [8/8] 列出部署后的 static/assets ===")
rc, out, err = ssh(f"ls -la {REMOTE_BASE}/backend/static/assets/")
print(out)

print("\n" + "=" * 60)
print("✅ 部署完成。请浏览器 Ctrl+F5 验证:")
print("  - 通知管理 → 群发系统公告 (持久化 + 历史)")
print("  - 审批管理 → 待我审批 (金额与项目列表一致)")
print("=" * 60)