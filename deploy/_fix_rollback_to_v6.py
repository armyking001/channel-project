"""修复 2026-09-08 v2: 完整回滚到 9/6 全量部署版本

诊断显示服务器问题:
1. config.yaml DB url 错 (被我改成 Z: 路径, 服务器是 Linux 不需要改)
2. models.py 已被上传新版本 (含 AnnouncementDraftHistory 表引用)
3. notifications_ws.py 已被上传新版本 (引用 AnnouncementDraftHistory)
4. systemd 一直 restart loop (status=3)

修复方案: 把 3 个文件全部回滚到部署时的原版本
"""
import subprocess, time
SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"
REMOTE_BASE = "/opt/channel-project"
BACKUP_DIR = "/opt/channel-project/backup_20260906"

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
    name = remote_path.split('/')[-1]
    tmp_path = f"/tmp/{name}"
    rc, out, err = scp(src, tmp_path, timeout)
    if rc != 0:
        return rc, out, err
    new_remote = remote_path + ".new"
    rc, out, err = ssh(f"sudo cp {tmp_path} {new_remote} && sudo chown root:root {new_remote} && sudo mv {new_remote} {remote_path} 2>&1")
    return rc, out, err

print("=" * 60)
print("FIX 2026-09-08 v2: 完整回滚到 9/6 版本")
print("=" * 60)

# [1] 看备份目录是否存在
print("\n=== [1] 检查 9/6 备份目录 ===")
rc, out, err = ssh(f"sudo ls -la {BACKUP_DIR} 2>&1 | head -10")
print(f"  exit={rc}\n{out}")

# [2] 停止服务 (彻底关掉 restart loop)
print("\n=== [2] 停止服务 ===")
rc, out, err = ssh("sudo systemctl stop channel-project; sleep 2; sudo systemctl is-active channel-project 2>&1; echo STOP_$?")
print(f"  exit={rc}\n{out}")

# [3] 从备份还原 3 个文件
print("\n=== [3] 从备份还原 3 个文件 ===")
files_to_restore = [
    (f"{BACKUP_DIR}/backend/app/models.py", f"{REMOTE_BASE}/backend/app/models.py"),
    (f"{BACKUP_DIR}/backend/app/routers/notifications_ws.py", f"{REMOTE_BASE}/backend/app/routers/notifications_ws.py"),
    (f"{BACKUP_DIR}/backend/config.yaml", f"{REMOTE_BASE}/backend/config.yaml"),
]
for src, dst in files_to_restore:
    rc, out, err = ssh(f"sudo ls -la {src} 2>&1")
    if rc != 0 or "No such file" in out:
        print(f"  ⚠️ 备份不存在: {src}")
        print(f"     out: {out.strip()}")
        # 试试 channel-project-data-backup-20260906125341
        alt = "/opt/channel-project-data-backup-20260906125341/backend/" + src.split('/backend/',1)[1] if '/backend/' in src else None
        if alt:
            rc2, out2, err2 = ssh(f"sudo ls -la {alt} 2>&1")
            print(f"     alt: {alt} -> {'OK' if rc2==0 else 'MISS'}")
            if rc2 == 0:
                src = alt
    rc, out, err = ssh(f"sudo cp {src} {dst} && sudo chown root:root {dst} 2>&1")
    print(f"  {src} -> {dst} exit={rc} {out.strip()}")

# [4] 验证 3 个文件已还原
print("\n=== [4] 验证文件 md5 ===")
rc, out, err = ssh(f"sudo md5sum {REMOTE_BASE}/backend/app/models.py {REMOTE_BASE}/backend/app/routers/notifications_ws.py {REMOTE_BASE}/backend/config.yaml")
print(f"  exit={rc}\n{out}")

# [5] 启动服务
print("\n=== [5] 启动服务 ===")
rc, out, err = ssh("sudo systemctl reset-failed channel-project 2>&1; sudo systemctl start channel-project; sleep 5; sudo systemctl is-active channel-project; echo START_$?")
print(f"  exit={rc}\n{out}")

# [6] 健康检查
print("\n=== [6] 健康检查 ===")
for i in range(10):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        break
    time.sleep(2)

# [7] nginx 健康检查
print("\n=== [7] nginx 健康检查 ===")
rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:26731/api/health 2>&1; echo")
print(f"  nginx /api/health -> {out.strip().split(chr(10))[0]}")

# [8] 看是否还有旧 uvicorn 干扰
print("\n=== [8] 进程列表 ===")
rc, out, err = ssh("ps -ef | grep -E 'uvicorn' | grep -v grep")
print(f"  exit={rc}\n{out}")

# [9] app_debug.log 最后错误
print("\n=== [9] app_debug.log 最后 30 行 ===")
rc, out, err = ssh("tail -30 /opt/channel-project/backend/app_debug.log 2>&1")
print(f"  exit={rc}\n{out}")

print("\n" + "=" * 60)
print("如果 [6]/[7] 都 200,服务已恢复。")
print("如果仍 502,把 [9] 输出贴给我继续诊断。")
print("=" * 60)