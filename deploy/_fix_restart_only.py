"""修复 2026-09-08: 服务器服务被停但未启动,只需 start service

不动任何文件,不动数据,只启动服务.
"""
import subprocess, time
SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"
REMOTE_BASE = "/opt/channel-project"

def ssh(cmd, timeout=30):
    r = subprocess.run(
        ["sshpass","-p",SSHPASS,"ssh","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10",
         f"{USER}@{SERVER}", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

print("=" * 60)
print("FIX 2026-09-08: 启动服务 (仅此一项,不动任何文件/数据)")
print("=" * 60)

print("\n=== [1] 当前状态 ===")
rc, out, err = ssh("sudo systemctl is-active channel-project 2>&1; echo ACTIVE_EXIT_$?")
print(f"  exit={rc}\n{out}")

print("\n=== [2] 启动服务 ===")
rc, out, err = ssh("sudo systemctl start channel-project; sleep 5; sudo systemctl is-active channel-project; echo START_EXIT_$?")
print(f"  exit={rc}\n{out}")

print("\n=== [3] 健康检查 ===")
for i in range(8):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        break
    time.sleep(2)

print("\n=== [4] 检查 static/assets (确认文件没被改动) ===")
rc, out, err = ssh(f"ls -la {REMOTE_BASE}/backend/static/assets/")
print(out)

print("\n=== [5] nginx 健康检查 ===")
rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:26731/api/health 2>&1; echo")
print(f"  nginx /api/health -> {out.strip().split(chr(10))[0]}")

print("\n" + "=" * 60)
print("✅ 服务应已恢复。请刷新浏览器 (Ctrl+F5)")
print("=" * 60)