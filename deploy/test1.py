"""Test scp directly 看真实错误"""
import subprocess
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
TAR = r'C:\Users\jwang\AppData\Local\Temp\channel-project-20260813160716.tar.gz'
r = subprocess.run([SCP, '-v', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
                    '-o', 'BatchMode=no', '-o', 'PreferredAuthentications=password',
                    TAR, 'admin001@172.16.10.92:/tmp/channel-project.tar.gz'],
                   capture_output=True, text=True, timeout=15)
print('rc:', r.returncode)
print('STDOUT (last 1000):', r.stdout[-1000:])
print('STDERR (last 500):', r.stderr[-500:])