"""找并杀掉 8765 占用的 uvicorn 进程, 再重新启动"""
import os, subprocess, sys, time, socket, signal

backend = r'z:\soft-RED\hermes\开发软件\渠道项目登记\backend'
log = os.path.join(backend, 'uvicorn_run.log')

# 找到占用 8765 的 python
import ctypes, ctypes.wintypes
out = subprocess.check_output(['powershell', '-NoProfile', '-Command',
    "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"
], text=True).strip()
pids = [int(x) for x in out.splitlines() if x.strip().isdigit()]
print("Listeners:", pids)

# 杀
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"kill pid {pid}")
    except Exception as e:
        print(f"kill pid {pid} err: {e}")
time.sleep(2)

# 再确认端口
s = socket.socket(); s.settimeout(0.5)
try:
    s.connect(("127.0.0.1", 8765)); s.close()
    print("port still listening (retry kill)"); sys.exit(1)
except: pass
print("port free")

# 重启
env = os.environ.copy()
env['PYTHONPATH'] = backend
venv_py = r'C:\Users\jwang\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
f = open(log, 'a', encoding='utf-8')
f.write(f"\n=== restart at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
p = subprocess.Popen(
    [venv_py, '-u', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8765', '--no-access-log'],
    cwd=backend, env=env, stdout=f, stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
print(f"new pid={p.pid}")
for i in range(20):
    time.sleep(1)
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 8765)); s.close()
        print(f"port ready @ {i+1}s")
        sys.exit(0)
    except: pass
print("port NOT ready")