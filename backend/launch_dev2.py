"""直接启动 uvicorn 并 detach, 不依赖 wrapper"""
import os, subprocess, sys, time, socket

BACKEND = r'z:\soft-RED\hermes\开发软件\渠道项目登记\backend'
LOG     = os.path.join(BACKEND, 'uvicorn_run.log')

# 优先 .venv_local -> .venv -> hermes-agent -> uv python -> 系统 python
venv_py = os.path.join(BACKEND, '.venv_local', 'Scripts', 'python.exe')
if not os.path.exists(venv_py):
    venv_py = os.path.join(BACKEND, '.venv', 'Scripts', 'python.exe')
if not os.path.exists(venv_py):
    venv_py = r'C:\Users\jwang\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
if not os.path.exists(venv_py):
    # 退回到当前 python
    venv_py = sys.executable

print("using python:", venv_py)

env = os.environ.copy()
env['PYTHONPATH'] = BACKEND

# 用 start /B 真正 detach 到新进程组
log = open(LOG, 'a', encoding='utf-8')
log.write(f"\n=== restart at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
log.write(f"python: {venv_py}\nPYTHONPATH: {env['PYTHONPATH']}\n")

# cmd start /B 不在沙箱里支持, 改用 Popen + CREATE_NEW_PROCESS_GROUP
p = subprocess.Popen(
    [venv_py, '-u', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8765', '--no-access-log'],
    cwd=BACKEND, env=env,
    stdout=log, stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
print(f"started pid={p.pid}")

# 等就绪
for i in range(25):
    time.sleep(1)
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(('127.0.0.1', 8765)); s.close()
        print(f"port ready @ {i+1}s")
        sys.exit(0)
    except Exception:
        pass
print("port NOT ready in 25s, see uvicorn_run.log")