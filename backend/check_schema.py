import sqlite3
conn = sqlite3.connect(r'C:\channel-data\data.db')
cur = conn.cursor()
print("=== projects table ===")
for row in cur.execute("PRAGMA table_info(projects)").fetchall():
    print(row)
print()
print("=== approval_logs table ===")
for row in cur.execute("PRAGMA table_info(approval_logs)").fetchall():
    print(row)
print()
print("=== users table ===")
for row in cur.execute("PRAGMA table_info(users)").fetchall():
    print(row)
print()
print("=== users count ===")
print(cur.execute("SELECT COUNT(*) FROM users").fetchone())
print("=== 刘建辉 user ===")
for row in cur.execute("SELECT * FROM users WHERE real_name='刘建辉'").fetchall():
    print(row)
print("=== Projects by 刘建辉 ===")
uid = cur.execute("SELECT id FROM users WHERE real_name='刘建辉'").fetchone()
if uid:
    uid = uid[0]
    print(f"user_id={uid}")
    print("projects where created_by=刘建辉:", cur.execute("SELECT COUNT(*) FROM projects WHERE created_by=?", (uid,)).fetchone())
    print("projects where approver_id=刘建辉:", cur.execute("SELECT COUNT(*) FROM projects WHERE approver_id=?", (uid,)).fetchone())
    print("approval_logs where approver_id=刘建辉:", cur.execute("SELECT COUNT(*) FROM approval_logs WHERE approver_id=?", (uid,)).fetchone())
    print("children where parent_id=刘建辉:", cur.execute("SELECT COUNT(*) FROM users WHERE parent_id=?", (uid,)).fetchone())
conn.close()
