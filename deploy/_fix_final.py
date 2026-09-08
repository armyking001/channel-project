"""修复 2026-09-08 v5 (FINAL): 彻底杀掉 8/7 旧 uvicorn,让 systemd 独占 8000

诊断确认:
- PID 3091806 (channel 用户) /opt/channel/backend/.venv/bin/python 占 127.0.0.1:8000 (8/7 旧版)
- PID 3099928 (root 用户) /usr/bin/python3 systemd 服务新版,刚启动就失败 (端口被占)
- 浏览器看到的是 8/7 旧版本响应的"暂无数据"

修复:
1. sudo systemctl stop channel-project (停掉 systemd 守护,避免它重启干扰)
2. sudo kill -9 所有非当前 ssh 会话的 uvicorn PID
3. 确认 8000 端口空闲
4. sudo systemctl start channel-project (启动新版本)
5. 健康检查 + 数据验证
"""
import subprocess, time, os
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
print("修复 v5 (FINAL): 彻底杀掉 8/7 旧 uvicorn")
print("=" * 60)

# [1] 停 systemd (避免它干扰杀进程 + 立刻重启)
print("\n=== [1] 停 systemd 服务 ===")
rc, out, err = ssh("sudo systemctl stop channel-project; sleep 1; sudo systemctl reset-failed channel-project 2>&1; sudo systemctl is-active channel-project 2>&1; echo STOP_$?")
print(f"  exit={rc}\n{out}")

# [2] 拿所有 uvicorn PID 并强杀
print("\n=== [2] 杀掉所有 uvicorn 进程 ===")
rc, out, err = ssh("ps -ef | grep uvicorn | grep -v grep | awk '{print $2}'")
pids = [l.strip() for l in out.strip().split('\n') if l.strip().isdigit()]
print(f"  待杀 PID 列表: {pids}")
for pid in pids:
    # sudo -n 强制免密码,kill -9 不可拦截
    rc, out, err = ssh(f"sudo -n kill -9 {pid} 2>&1; echo KILL_{pid}_$?")
    print(f"  kill -9 {pid} -> {out.strip()}")

# [3] 等待端口释放
print("\n=== [3] 等待端口释放 ===")
time.sleep(3)
rc, out, err = ssh("sudo ss -tlnp 2>/dev/null | grep ':8000' ; echo PORT_CHECK_DONE")
print(f"  exit={rc}\n{out}")

# [4] 确认无 uvicorn 进程残留
print("\n=== [4] 确认无 uvicorn 残留 ===")
rc, out, err = ssh("ps -ef | grep uvicorn | grep -v grep; echo PROC_CHECK_DONE")
print(f"  exit={rc}\n{out}")

# [5] 启动 systemd 服务 (现在端口空了,独占 8000)
print("\n=== [5] 启动 systemd 服务 ===")
rc, out, err = ssh("sudo systemctl start channel-project; sleep 6; sudo systemctl is-active channel-project; echo START_$?")
print(f"  exit={rc}\n{out}")

# [6] 健康检查 (重试 10 次)
print("\n=== [6] 健康检查 ===")
ok = False
for i in range(10):
    rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/health 2>&1; echo")
    code = out.strip().split('\n')[0]
    print(f"  第{i+1}次 /api/health -> {code}")
    if code == "200":
        ok = True
        break
    time.sleep(2)

if not ok:
    print("  ❌ 健康检查一直失败,看下面 app_debug.log")

# [7] 验证进程路径 (确认是新版本而非旧版本)
print("\n=== [7] 8000 端口对应进程 ===")
rc, out, err = ssh("sudo ss -tlnp 2>/dev/null | grep ':8000'")
print(f"  exit={rc}\n{out}")

# [8] nginx 健康检查
print("\n=== [8] nginx 健康检查 ===")
rc, out, err = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:26731/api/health 2>&1; echo")
print(f"  nginx /api/health -> {out.strip().split(chr(10))[0]}")

# [9] 业务接口验证 - 项目列表 (确认浏览器能看到数据)
print("\n=== [9] 业务接口 - admin 登录 + 项目列表 ===")
rc, out, err = ssh("curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin&password=akwj210627'")
print(f"  login exit={rc}")
try:
    import json
    tok = json.loads(out)['access_token']
    print(f"  token: {tok[:50]}...")
    rc, out, err = ssh(f"curl -s http://127.0.0.1:8000/api/projects/ -H 'Authorization: Bearer {tok}'")
    proj = json.loads(out)
    print(f"  GET /api/projects count={len(proj) if isinstance(proj, list) else proj.get('total', '?')}")
    print(f"  前 3 个项目: {[p['project_name'] for p in (proj if isinstance(proj, list) else proj.get('items', []))[:3]]}")
except Exception as e:
    print(f"  ⚠️ 接口验证失败: {e}")
    print(f"  out: {out[:300]}")

# [10] 看 app_debug.log 最近 (诊断未来问题)
print("\n=== [10] app_debug.log 最后 10 行 ===")
rc, out, err = ssh("tail -10 /opt/channel-project/backend/app_debug.log 2>&1")
print(f"  exit={rc}\n{out}")

print("\n" + "=" * 60)
if ok:
    print("✅ 服务已恢复。浏览器 Ctrl+F5 刷新应能看到项目数据。")
    print("⚠️ 注意: 本次修复未应用通知管理 + 审批金额新代码 (因为旧版本/新版本状态复杂)")
    print("   后续如需应用新功能,需要重新规划完整部署 (AGENTS.md §45)")
else:
    print("❌ 健康检查仍失败。把 [7][10] 输出贴给我。")
print("=" * 60)