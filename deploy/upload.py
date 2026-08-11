"""Direct upload via sshpass subprocess with full output"""
import subprocess
import os
import sys

SSHPASS = r"C:\Users\jwang\AppData\Local\Microsoft\WindowsApps\sshpass.exe"
TAR_FILE = r"C:\Users\jwang\AppData\Local\Temp\channel-project-20260807084323.tar.gz"
PASSWORD = "akwj210627"
SERVER = "admin001@172.16.10.92"
REMOTE_PATH = "/tmp/channel-project.tar.gz"

if not os.path.exists(TAR_FILE):
    print(f"ERROR: tarball not found: {TAR_FILE}")
    sys.exit(1)

print(f"[INFO] Uploading {TAR_FILE} ({os.path.getsize(TAR_FILE) / 1024 / 1024:.2f} MB)")
print(f"[INFO] To: {SERVER}:{REMOTE_PATH}")
print()

# Write password to file
PWD_FILE = r"C:\Users\jwang\AppData\Local\Temp\sshpass_pwd.tmp"
with open(PWD_FILE, 'w') as f:
    f.write(PASSWORD)

# Run sshpass scp
result = subprocess.run(
    [SSHPASS, "-f", PWD_FILE, "scp",
     "-o", "StrictHostKeyChecking=no",
     "-o", "UserKnownHostsFile=NUL",
     "-o", "ConnectTimeout=30",
     TAR_FILE, f"{SERVER}:{REMOTE_PATH}"],
    capture_output=True,
    text=True,
    timeout=60,
)

print(f"[INFO] Exit code: {result.returncode}")
print(f"[STDOUT] {result.stdout}")
print(f"[STDERR] {result.stderr}")

# Cleanup
try:
    os.remove(PWD_FILE)
except OSError:
    pass

if result.returncode == 0:
    print("\n[SUCCESS] Upload complete!")
else:
    print("\n[FAILED] Upload failed")
    sys.exit(1)