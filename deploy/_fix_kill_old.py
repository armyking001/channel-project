"""修复 2026-09-08 v3: 杀掉 8/7 旧 uvicorn 释放 8000 端口

根因: /opt/channel/backend/.venv/bin/python (8/7 部署) 占着 127.0.0.1:8000
    systemd 服务 (/opt/channel-project/) 新版本启动时端口被占 → fail

修复: kill PID 2941812,让 systemd 服务独占 8000 端口
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
        capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

print("=" * 60)
print("FIX 2026-09-08 v3: 杀掉 8/7 旧 uvicorn,释放 8000")
print("=" * 60)

# [1] 看 8000 端口占用
print("\n=== [1] 8000 端口占用 ===")
rc, out, err = ssh("sudo ss -tlnp | grep ':8000' 2>&1; sudo lsof -i:8000 2>&1 | head -5")
print(f"  exit={rc}\n{out}")

# [2] 看所有 uvicorn 进程
print("\n=== [2] 所有 uvicorn 进程 ===")
rc, out, err = ssh("ps -ef | grep uvicorn | grep -v grep")
print(f"  exit={rc}\n{out}")

# [3] 停止 systemd 服务
print("\n=== [3] 停止 systemd 服务 ===")
rc, out, err = ssh("sudo systemctl stop channel-project; sleep 2; sudo systemctl reset-failed channel-project; sudo systemctl is-active channel-project 2>&1; echo STOP_$?")
print(f"  exit={rc}\n{out}")

# [4] 杀掉所有 uvicorn 进程(包括 8/7 旧版本)
print("\n=== [4] 杀掉所有 uvicorn 进程 ===")
# 先 grep 拿到 PID 列表
rc, out, err = ssh("ps -ef | grep uvicorn | grep -v grep | awk '{print $2}'")
pids = [l.strip() for l in out.strip().split('\n') if l.strip()]
print(f"  待杀 PID: {pids}")
for pid in pids:
    rc, out, err = ssh(f"sudo kill -9 {pid} 2>&1; echo KILL_{pid}_$?")
    print(f"  kill {pid} -> {out.strip()}")

# [5] 确认 8000 端口空闲
print("\n=== [5] 确认 8000 端口空闲 ===")
rc, out, err = ssh("sleep 2; sudo ss -tlnp | grep ':8000' 2>&1; echo PORT_CHECK_DONE")
print(f"  exit={rc}\n{out}")

# [6] 启动 systemd 服务
print("\n=== [6] 启动 systemd 服务 ===")
rc, out, err = ssh("sudo systemctl start channel-project; sleep 6; sudo systemctl is-active channel-project; echo START_$?")
print(f"  exit={rc}\n{out}")

# [7] 健康检查
print("\n=== [7] 健康检查 ===")
for i in range(10):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        break
    time.sleep(2)

# [8] nginx 健康检查
print("\n=== [8] nginx 健康检查 ===")
rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:26731/api/health 2>&1; echo")
print(f"  nginx /api/health -> {out.strip().split(chr(10))[0]}")

# [9] 现在进程列表
print("\n=== [9] 进程列表 ===")
rc, out, err = ssh("ps -ef | grep uvicorn | grep -v grep")
print(f"  exit={rc}\n{out}")

# [10] app_debug.log 最后 20 行
print("\n=== [10] app_debug.log 最后 20 行 ===")
rc, out, err = ssh("tail -20 /opt/channel-project/backend/app_debug.log 2>&1")
print(f"  exit={rc}\n{out}")

print("\n" + "=" * 60)
print("预期: [7]/[8] 200")
print("如果仍失败,把 [10] 输出贴给我")
print("=" * 60)