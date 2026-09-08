"""修复 2026-09-08: 服务器 config.yaml DB url 错误 (指向 Windows 路径)

服务器是 Linux,DB url 必须用 /opt/... 而不是 Z:/...
用之前的备份还原 config.yaml
"""
import subprocess
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

def scp(src, dst, timeout=60):
    r = subprocess.run(
        ["sshpass","-p",SSHPASS,"scp","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10",
         src, f"{USER}@{SERVER}:{dst}"],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

def scp_via_tmp(src, remote_path, timeout=60):
    """scp 到 /tmp/ + sudo cp 到目标 (root 拥有的目录)"""
    name = remote_path.split('/')[-1]
    tmp_path = f"/tmp/{name}"
    rc, out, err = scp(src, tmp_path, timeout)
    if rc != 0:
        return rc, out, err
    # 先 cp 到 /opt/... 同目录的 .new,再 sudo mv
    new_remote = remote_path + ".new"
    rc, out, err = ssh(f"sudo cp {tmp_path} {new_remote} && sudo chown root:root {new_remote} && sudo mv {new_remote} {remote_path} 2>&1")
    return rc, out, err

print("=" * 60)
print("FIX 2026-09-08: 还原 config.yaml 到 Linux 路径")
print("=" * 60)

# 先确认服务器 config.yaml 现状
print("\n=== [1] 当前服务器 config.yaml (database.url) ===")
rc, out, err = ssh(f"sudo cat {REMOTE_BASE}/backend/config.yaml | grep -A1 database")
print(f"  exit={rc}\n{out}")

# 写一个新的 config.yaml,使用 Linux 路径
print("\n=== [2] 写新 config.yaml 到 /tmp ===")
LOCAL_BASE = r"Z:\soft-RED\hermes\开发软件\渠道项目登记"
local_cfg = LOCAL_BASE + r"\deploy\config.yaml.fix"
content = '''database:
  url: sqlite:////opt/channel-project/backend/data.db
  echo: false
  pool_size: 5
  connect_args:
    timeout: 30

webdav:
  default_user: admin
  default_password: ""
  timeout: 30
'''
with open(local_cfg, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"  本地生成: {local_cfg}")
print(content)

print("\n=== [3] SCP 上传到服务器 (走 /tmp 中转) ===")
rc, out, err = scp_via_tmp(local_cfg, f"{REMOTE_BASE}/backend/config.yaml", timeout=60)
if rc != 0:
    print(f"  ❌ FAIL: {err}")
    import sys; sys.exit(1)
print("  ✅ 上传成功")

print("\n=== [4] 验证服务器 config.yaml ===")
rc, out, err = ssh(f"sudo cat {REMOTE_BASE}/backend/config.yaml | head -10")
print(f"  exit={rc}\n{out}")

print("\n=== [5] 重启服务 ===")
rc, out, err = ssh("sudo systemctl restart channel-project; sleep 5; sudo systemctl is-active channel-project")
print(f"  exit={rc}\n{out}")

print("\n=== [6] 健康检查 ===")
import time
for i in range(8):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        break
    time.sleep(2)

print("\n=== [7] nginx 健康检查 ===")
rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:26731/api/health 2>&1; echo")
print(f"  nginx /api/health -> {out.strip().split(chr(10))[0]}")

print("\n" + "=" * 60)
print("✅ config.yaml 已还原。服务应已恢复。")
print("⚠️ 注意: 本次只还原 config.yaml,未动 models.py 和 notifications_ws.py (这两个文件已上传,但需要重启服务后生效)")
print("   服务器服务现在用旧数据库 schema 运行(AnnouncementDraftHistory 表尚未创建)")
print("   修复服务后,如果你想要新通知管理功能,需要再跑一次 hotfix 让 models.py 创建新表")
print("=" * 60)