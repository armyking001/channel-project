"""启动 uvicorn (FastAPI)"""
import os
import sys
import subprocess
import time

backend_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(backend_dir, 'app_debug.log')
port = 8765

# 优先使用项目本地 .venv_local，避免依赖旧盘符或已失效的 venv 路径
venv_python = os.path.join(backend_dir, '.venv_local', 'Scripts', 'python.exe')
if not os.path.exists(venv_python):
    venv_python = os.path.join(backend_dir, '.venv', 'Scripts', 'python.exe')
if os.path.exists(venv_python):
    python_exe = venv_python
    print(f"使用 venv python: {python_exe}")
else:
    # 用系统 python
    python_exe = sys.executable
    print(f"使用系统 python: {python_exe}")

env = os.environ.copy()
site_packages = os.path.join(os.path.dirname(python_exe), 'Lib', 'site-packages')
python_paths = [os.environ.get('PYTHONPATH'), backend_dir]
if os.path.isdir(site_packages):
    python_paths.insert(0, site_packages)
env['PYTHONPATH'] = os.pathsep.join(path for path in python_paths if path)
print(f"PYTHONPATH={env.get('PYTHONPATH')}")

# 启动 uvicorn，禁用 reload，监听 8765（Windows 8000 端口可能被 Hyper-V 保留）
cmd = [python_exe, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', str(port)]
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
        s.connect(('127.0.0.1', port))
        s.close()
        print(f"✓ 端口 {port} 已就绪 ({i+1}s)")
        sys.exit(0)
    except Exception:
        pass
print(f"✗ 端口 {port} 未在 15s 内就绪")
sys.exit(1)
