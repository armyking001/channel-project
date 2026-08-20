"""上传 diag_db.py 到服务器并运行"""
import winpty, time, sys

SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
SSH_HOST = '172.16.10.92'
SSH_USER = 'admin001'
SSH_PASS = 'akwj210627'
SCRIPT = r'z:\soft-RED\hermes\开发软件\渠道项目登记\deploy\diag_db.py'


def run_pty(cmd, timeout=20, feeds=None):
    p = winpty.PtyProcess.spawn(cmd, dimensions=(40, 200))
    out = ''
    sent = False
    start = time.time()
    while time.time() - start < timeout:
        try:
            chunk = p.read(8192)
            if chunk:
                if isinstance(chunk, bytes): chunk = chunk.decode('utf-8', errors='ignore')
                out += chunk
                sys.stdout.write(chunk)
                sys.stdout.flush()
                if not sent and 'password' in out.lower():
                    time.sleep(0.3)
                    p.write(SSH_PASS + '\r\n')
                    sent = True
        except EOFError:
            break
        except Exception:
            break
        if not p.isalive():
            break
        time.sleep(0.05)
    if p.isalive():
        p.terminate(force=True)
    return p.exitstatus


# 1. 上传
print('[Upload diag_db.py]')
run_pty([SCP, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
         '-o', 'PreferredAuthentications=password',
         SCRIPT, f'{SSH_USER}@{SSH_HOST}:/tmp/diag_db.py'], timeout=30)

# 2. 运行
print('\n[Run diag_db.py]')
run_pty([SSH, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
         '-o', 'PreferredAuthentications=password',
         f'{SSH_USER}@{SSH_HOST}',
         'sudo python3 /tmp/diag_db.py'], timeout=20)
print('---done')