"""直接查服务器数据库找 admin 密码"""
import winpty, time, sys

SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'

p = winpty.PtyProcess.spawn(
    [SSH, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
     '-o', 'PreferredAuthentications=password',
     'admin001@172.16.10.92',
     "sudo sqlite3 /opt/channel-project/backend/data.db \"SELECT id, username, real_name, role, is_active FROM users WHERE role='admin' OR username='admin'\""],
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
                p.write('akwj210627\r\n')
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