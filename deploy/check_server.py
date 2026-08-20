"""检查服务器端 approvals.py 是否有最新修复"""
import winpty, time, sys

SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SSH_HOST = '172.16.10.92'
SSH_USER = 'admin001'
SSH_PASS = 'akwj210627'

p = winpty.PtyProcess.spawn(
    [SSH, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
     '-o', 'PreferredAuthentications=password',
     f'{SSH_USER}@{SSH_HOST}',
     'sudo cat /opt/channel-project/backend/app/routers/approvals.py | head -160 | tail -50'],
    dimensions=(40, 200))
out = ''
sent = False
start = time.time()
while time.time() - start < 15:
    try:
        chunk = p.read(8192)
        if chunk:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8', errors='ignore')
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
if p.isalive(): p.terminate(force=True)
print('\n---exit:', p.exitstatus)