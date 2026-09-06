import subprocess
import sys
import time

# 用 netstat 找进程
out = subprocess.run('netstat -ano | findstr ":8000"', shell=True, capture_output=True, text=True)
print("netstat output:")
print(out.stdout)
print("---")
if out.returncode == 0:
    for line in out.stdout.splitlines():
        if ":8000" in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                try:
                    pid = int(parts[-1])
                    print(f"Found PID: {pid}")
                except ValueError:
                    pass
else:
    print("No process listening on 8000")
