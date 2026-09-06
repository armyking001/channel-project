"""检查 data.db 文件权限并尝试修复"""
import os
import subprocess
import time

db_path = r'C:\channel-data\data.db'
db_dir = r'C:\channel-data'

# 1. 文件是否存在
print(f"db exists: {os.path.exists(db_path)}")
print(f"db size: {os.path.getsize(db_path) if os.path.exists(db_path) else 'N/A'}")

# 2. 当前权限
print("\n=== 当前权限 ===")
out = subprocess.run(f'icacls "{db_path}"', shell=True, capture_output=True, text=True)
print(out.stdout)

# 3. 目录权限
print("\n=== 目录权限 ===")
out = subprocess.run(f'icacls "{db_dir}"', shell=True, capture_output=True, text=True)
print(out.stdout)

# 4. 尝试直接写
print("\n=== 尝试 sqlite3 写入 ===")
import sqlite3
try:
    c = sqlite3.connect(db_path, timeout=10)
    c.execute("PRAGMA journal_mode=MEMORY")
    c.execute("BEGIN")
    c.execute("UPDATE users SET is_active=1 WHERE id=1")
    c.commit()
    print("✓ 写入成功")
    c.close()
except Exception as e:
    print(f"✗ 写入失败: {e}")
