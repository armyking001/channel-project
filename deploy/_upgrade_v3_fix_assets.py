"""升级 v3: 上传新 bundle 到服务器 assets/,与 index.html 引用对齐

范围: 仅 static/assets/index-XZPlD_zl.js + index-D0_cB0gD.css
不动: config.yaml / models.py / notifications_ws.py / data.db / 其他所有文件
不需要重启服务 (Python 进程不用重启)
"""
import subprocess, os, time
SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"
REMOTE_BASE = "/opt/channel-project"
LOCAL_BASE = r"Z:\soft-RED\hermes\开发软件\渠道项目登记"

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

print("=" * 60)
print("升级 v3: 上传新 bundle 到 assets/")
print("=" * 60)

# [1] 备份服务器 assets/ 目录当前内容
print("\n=== [1] 备份服务器当前 assets/ ===")
ts = time.strftime('%Y%m%d_%H%M%S')
backup_dir = f"/tmp/assets_backup_{ts}"
rc, out, err = ssh(f"sudo mkdir -p {backup_dir}; sudo cp -r /opt/channel-project/backend/static/assets/* {backup_dir}/; sudo chown -R admin001:admin001 {backup_dir}; sudo ls -la {backup_dir}")
print(f"  exit={rc}\n{out}")

# [2] 上传新 bundle 和 css (走 /tmp 中转 + sudo cp)
print("\n=== [2] 上传新 bundle 和 css ===")
files_to_upload = [
    (LOCAL_BASE + r"\backend\static\assets\index-XZPlD_zl.js", "index-XZPlD_zl.js"),
    (LOCAL_BASE + r"\backend\static\assets\index-D0_cB0gD.css", "index-D0_cB0gD.css"),
]
for local, name in files_to_upload:
    local_unix = local.replace('\\','/')
    sz = os.path.getsize(local)
    print(f"  -> {name} ({sz:,} bytes)")
    # scp 到 /tmp/
    rc, out, err = scp(local_unix, f"/tmp/{name}")
    if rc != 0:
        print(f"  ❌ scp 失败: {err}")
        import sys; sys.exit(1)
    # sudo cp 到 assets/
    rc, out, err = ssh(f"sudo cp /tmp/{name} /opt/channel-project/backend/static/assets/{name} && sudo chown root:root /opt/channel-project/backend/static/assets/{name}")
    if rc != 0:
        print(f"  ❌ sudo cp 失败: {err}")
        import sys; sys.exit(1)
    print(f"  ✅ {name} 已上传")

# [3] 验证 assets/ 目录现在有 4 个文件
print("\n=== [3] 验证 assets/ ===")
rc, out, err = ssh("sudo ls -la /opt/channel-project/backend/static/assets/")
print(f"  exit={rc}\n{out}")

# [4] nginx 健康检查 (确认新 bundle 可访问)
print("\n=== [4] nginx 加载新 bundle ===")
rc, out, err = ssh("curl -s -o /dev/null -w 'index.html: %{http_code}\n' http://127.0.0.1:26731/admin/")
print(out.strip())
rc, out, err = ssh("curl -s -o /dev/null -w 'bundle js: %{http_code}\n' http://127.0.0.1:26731/admin/assets/index-XZPlD_zl.js")
print(out.strip())
rc, out, err = ssh("curl -s -o /dev/null -w 'css: %{http_code}\n' http://127.0.0.1:26731/admin/assets/index-D0_cB0gD.css")
print(out.strip())

# [5] 后端 health (确认服务还在跑)
print("\n=== [5] 后端 health ===")
rc, out, err = ssh("curl -s http://127.0.0.1:8000/api/health")
print(f"  {out.strip()}")
rc, out, err = ssh("curl -s -o /dev/null -w 'nginx health: %{http_code}\n' http://127.0.0.1:26731/api/health")
print(out.strip())

# [6] 业务接口验证
print("\n=== [6] 业务接口 ===")
rc, out, err = ssh("curl -s -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=admin&password=akwj210627'")
try:
    import json
    tok = json.loads(out)['access_token']
    rc, out, err = ssh(f"curl -s 'http://127.0.0.1:8000/api/projects/?approval_status=pending' -H 'Authorization: Bearer {tok}' | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"pending count:\",len(d) if isinstance(d,list) else d.get(\"total\",\"?\"))'")
    print(f"  {out.strip()}")
except Exception as e:
    print(f"  ⚠️ 验证失败: {e}")

print("\n" + "=" * 60)
print("✅ 上传完成。请浏览器 Ctrl+F5 刷新验证:")
print("  - 项目列表能看到数据")
print("  - 审批管理金额列与项目列表一致")
print("=" * 60)