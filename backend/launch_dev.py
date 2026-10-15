"""用 cmd.exe start /B 启动uvicorn, 让进程脱离此 Python 沙箱独立存活"""
import os, subprocess, time, socket

backend = r"Z:\soft-RED\hermes\开发软件\渠道项目登记\backend"
log = os.path.join(backend, "_dev_uvicorn.log")
pid_file = os.path.join(backend, "_launch_dev.pid")

# 先清空旧log
open(log, "w").close()

# 用 cmd.exe 启动, 走 start /B 真正的detach (sandbox 下最可靠)
# 注意: 必须把 stdout/stderr 重定向到文件, 否则 sandbox 回收时会丢失
cmd = (
    f'cd /d "{backend}" && '
    f'start /B "" "{os.path.join(os.path.dirname(os.sys.executable) if False else "", "python.exe")}" '
    f'-u -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --no-access-log '
    f'>> "{log}" 2>&1'
)
# 上面 sys.executable 不可靠, 改用 hermes-agent venv 里的 python
venv_py = r"C:\Users\jwang\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
cmd = (
    f'cd /d "{backend}" && '
    f'start /B "" "{venv_py}" '
    f'-u -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --no-access-log '
    f'>> "{log}" 2>&1'
)
print("CMD:", cmd)
rc = subprocess.run(cmd, shell=True)
print("rc:", rc.returncode)

# 等就绪
for i in range(20):
    time.sleep(1)
    try:
        s = socket.socket(); s.settimeout(0.5)
        s.connect(("127.0.0.1", 8765)); s.close()
        print(f"OK 端口就绪 @ {i+1}s")
        break
    except Exception:
        pass
else:
    print("FAIL 端口未就绪")