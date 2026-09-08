"""检查服务器端代码 (只读, 0 改动):
- 后端 models.py 是否含 AnnouncementDraftHistory
- 后端 notifications_ws.py 是否含 3 个新接口
- 前端 bundle hash 是否最新
- DB 是否已创建新表
"""
import subprocess, re, os, time, hashlib

SSHPASS = "akwj210627"
SERVER = "172.16.10.92"
USER = "admin001"
REMOTE_BASE = "/opt/channel-project"

def ssh(cmd, timeout=30):
    r = subprocess.run(
        ["sshpass","-p",SSHPASS,"ssh","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10",
         "-o","RequestTTY=no",
         f"{USER}@{SERVER}", cmd],
        capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr

def clean(text):
    """去除 ANSI 终端控制字符 + prompt 残留"""
    return re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)

def grep_count(cmd):
    """执行 grep -c 并返回干净的整数"""
    rc, out, err = ssh(cmd)
    out_clean = clean(out).strip()
    lines = [l for l in out_clean.split('\n') if l.strip().isdigit()]
    return lines[-1] if lines else "0", clean(out)

print("=" * 60)
print("检查服务器端代码状态 (只读)")
print("=" * 60)

# [1] models.py
print("\n=== [1] models.py 是否含 AnnouncementDraftHistory ===")
count, raw = grep_count(f"sudo grep -c 'class AnnouncementDraftHistory' {REMOTE_BASE}/backend/app/models.py")
print(f"  匹配行数: {count}")
if count != "0":
    rc, out, _ = ssh(f"sudo grep -n 'class AnnouncementDraftHistory\\|announcement_draft_history\\|source.*draft.*history' {REMOTE_BASE}/backend/app/models.py | head -10")
    print(f"  详情:\n{clean(out)}")

# [2] notifications_ws.py
print("\n=== [2] notifications_ws.py 是否含 3 个新接口 ===")
count, raw = grep_count(f"sudo grep -c 'announce/draft\\|/announce/history' {REMOTE_BASE}/backend/app/routers/notifications_ws.py")
print(f"  匹配行数: {count}")
if count != "0":
    rc, out, _ = ssh(f"sudo grep -n '/announce/draft\\|/announce/history' {REMOTE_BASE}/backend/app/routers/notifications_ws.py | head -10")
    print(f"  详情:\n{clean(out)}")

# [3] 前端 index.html 引用 hash
print("\n=== [3] 前端 index.html 引用 hash ===")
rc, out, _ = ssh(f"sudo grep -o 'index-[A-Za-z0-9_-]*\\.js' {REMOTE_BASE}/backend/static/index.html")
print(f"  引用: {clean(out).strip()}")

# [4] 前端 assets 目录
print("\n=== [4] 前端 assets 目录 ===")
rc, out, _ = ssh(f"sudo ls -la {REMOTE_BASE}/backend/static/assets/")
print(clean(out))

# [5] 本地 bundle
print("\n=== [5] 本地构建产物 ===")
local_html = r"Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\static\index.html"
print(f"  本地 index.html: {time.ctime(os.path.getmtime(local_html))}")
assets_dir = r"Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\static\assets"
for f in sorted(os.listdir(assets_dir)):
    fp = os.path.join(assets_dir, f)
    print(f"  {f} ({os.path.getsize(fp):,} B) {time.ctime(os.path.getmtime(fp))}")

# [6] 服务器 DB 表
print("\n=== [6] 服务器 DB 表 (含 announce/draft) ===")
rc, out, _ = ssh(f"sudo sqlite3 {REMOTE_BASE}/backend/data.db \".tables\" 2>&1")
tables = clean(out).strip()
all_tables = [t for t in tables.split() if t]
print(f"  总表数: {len(all_tables)}")
print(f"  含 announce/draft 的表: {[t for t in all_tables if 'announce' in t.lower() or 'draft' in t.lower()]}")

# [7] announcement_draft_history 行数
print("\n=== [7] announcement_draft_history 行数 ===")
rc, out, _ = ssh(f"sudo sqlite3 {REMOTE_BASE}/backend/data.db 'SELECT count(*) FROM announcement_draft_history;' 2>&1")
print(f"  exit={rc} 行数={clean(out).strip()}")

# [8] 表结构
print("\n=== [8] announcement_draft_history 表结构 ===")
rc, out, _ = ssh(f"sudo sqlite3 {REMOTE_BASE}/backend/data.db \".schema announcement_draft_history\" 2>&1")
print(f"  exit={rc}\n{clean(out)}")

# [9] 后端代码 md5 对比
print("\n=== [9] 后端代码 md5 对比 (本地 vs 服务器) ===")
for local_rel, remote_rel in [
    (r"Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\app\models.py", f"{REMOTE_BASE}/backend/app/models.py"),
    (r"Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\app\routers\notifications_ws.py", f"{REMOTE_BASE}/backend/app/routers/notifications_ws.py"),
]:
    local_md5 = hashlib.md5(open(local_rel, 'rb').read()).hexdigest()
    rc, out, _ = ssh(f"sudo md5sum {remote_rel}")
    out_clean = clean(out).strip()
    remote_md5 = out_clean.split()[0] if out_clean else ""
    name = os.path.basename(local_rel)
    same = "✅ 一致" if local_md5 == remote_md5 else "❌ 不一致"
    print(f"  {name}: 本地 {local_md5} | 服务器 {remote_md5 or '(无输出)'} | {same}")

print("\n" + "=" * 60)
print("结论 (基于以上输出):")
print("=" * 60)