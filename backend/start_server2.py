"""后端启动脚本 v2（使用 .venv_local_new_pkgs 临时包 + uv-cpython 解释器）

用法：
    python start_server2.py

行为：
- 自动设置 PYTHONPATH 指向 backend 源码目录与 .venv_local_new_pkgs/（系统 python pip 装的临时包）
- 通过 python -m uvicorn 启动，监听 0.0.0.0:8765
"""
import os
import subprocess
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BACKEND_DIR, 'uvicorn_run.log')

# 用 hermes-agent 的 venv Python（已装 fastapi / pydantic / pydantic_core 带 .pyd），
# 但该 venv 缺 sqlalchemy / webdavclient3 / openpyxl / xlrd / passlib / jose / openai / chromadb 等。
# 把后端本地的 site_pkg 和 .venv_local_new_pkgs 通过 sitecustomize 追加到 sys.path 末尾，
# 这样 hermes-agent venv 里已经装好的带二进制扩展的包仍会被优先使用。
EXTRA_SITE_PKG = os.path.join(BACKEND_DIR, 'site_pkg')           # sqlalchemy / openpyxl / xlrd / passlib / jose / webdav3
EXTRA_AI_PKGS = os.path.join(BACKEND_DIR, '.venv_local_new_pkgs')  # openai / chromadb / webdavclient3

os.environ['PYTHONPATH'] = BACKEND_DIR

# sitecustomize.py 已经在源仓库里写好（基于 _here 动态计算路径），不要在这里覆盖
# 如果需要重写，删掉 backend/sitecustomize.py 即可。

cmd = [
    sys.executable,
    '-m',
    'uvicorn',
    'app.main:app',
    '--host',
    '0.0.0.0',
    '--port',
    '8765',
]

print(f"启动命令: {' '.join(cmd)}")
print(f"PYTHONPATH={os.environ['PYTHONPATH']}")

with open(LOG_FILE, 'a', encoding='utf-8') as f:
    f.write(f"\n=== restart at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    f.write(f"cmd: {' '.join(cmd)}\n")
    f.write(f"PYTHONPATH: {os.environ['PYTHONPATH']}\n")
    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)