"""启动 uvicorn (FastAPI)"""
import os
import sys
import subprocess
import time

backend_dir = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend'
log_file = os.path.join(backend_dir, 'app_debug.log')

# 启动 uvicorn，禁用 reload，监听 8000
# 使用 .venv 内的 Python (uv 安装)
# 通过 .venv/Scripts/python.exe -m uvicorn ...
# 检查 .venv 是否存在
venv_python = os.path.join(backend_dir, '.venv', 'Scripts', 'python.exe')
if os.path.exists(venv_python):
    python_exe = venv_python
    print(f"使用 venv python: {python_exe}")
else:
    # 用系统 python
    python_exe = sys.executable
    print(f"使用系统 python: {python_exe}")

env = os.environ.copy()
env['PYTHONPATH'] = os.path.join(backend_dir, '.venv', 'Lib', 'site-packages') + ';' + backend_dir
# 同时把 site-packages 也加进去
import glob
sp = glob.glob(os.path.join(backend_dir, '.venv', 'Lib', 'site-packages'))
if sp:
    env['PYTHONPATH'] = ';'.join(sp + [backend_dir])
print(f"PYTHONPATH={env.get('PYTHONPATH')}")

# 启动 uvicorn
cmd = [python_exe, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000']
print(f"启动命令: {' '.join(cmd)}")

# 后台启动
log_fh = open(log_file, 'a', encoding='utf-8')
proc = subprocess.Popen(
    cmd,
    cwd=backend_dir,
    env=env,
    stdout=log_fh,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
)
print(f"uvicorn PID: {proc.pid}")

# 等待启动
for i in range(15):
    time.sleep(1)
    try:
        import socket
        s = socket.socket()
        s.settimeout(1)
        s.connect(('127.0.0.1', 8000))
        s.close()
        print(f"✓ 端口 8000 已就绪 ({i+1}s)")
        sys.exit(0)
    except Exception:
        pass
print("✗ 端口 8000 未在 15s 内就绪")
sys.exit(1)
