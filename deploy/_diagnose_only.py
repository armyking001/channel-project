"""诊断 2026-09-08: 服务 activating 但 health=000

只读日志 + systemctl status,不动任何文件.
"""
import subprocess
SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"

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
print("诊断 2026-09-08: 服务无法启动")
print("=" * 60)

print("\n=== [1] systemctl status ===")
rc, out, err = ssh("sudo systemctl status channel-project --no-pager -l 2>&1 | head -50")
print(f"  exit={rc}\n{out}")

print("\n=== [2] 最近 80 行 journalctl ===")
rc, out, err = ssh("sudo journalctl -u channel-project -n 80 --no-pager -o short 2>&1")
print(f"  exit={rc}\n{out}")

print("\n=== [3] 进程是否真在 ===")
rc, out, err = ssh("ps -ef | grep -E 'uvicorn|channel-project' | grep -v grep")
print(f"  exit={rc}\n{out}")

print("\n=== [4] 端口 8000 ===")
rc, out, err = ssh("ss -tlnp 2>/dev/null | grep ':8000' ; sudo ss -tlnp | grep ':8000'")
print(f"  exit={rc}\n{out}")

print("\n=== [5] app_debug.log 最后 50 行 ===")
rc, out, err = ssh("tail -50 /opt/channel-project/backend/app_debug.log 2>&1")
print(f"  exit={rc}\n{out}")

print("\n=== [6] 手动启动一次 (10秒) 抓真实报错 ===")
rc, out, err = ssh("cd /opt/channel-project/backend && timeout 10 sudo -u www-data bash -c 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' 2>&1 | head -60")
print(f"  exit={rc}\n{out}")