"""Phase 0.1 - DB 数据快照 (只读, 不动 DB)"""
import sqlite3
c = sqlite3.connect(r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\data.db')
cur = c.cursor()

print('===== projects =====')
for r in cur.execute('''SELECT id, project_name, source, responsible_sales,
                            created_by, storage_zone_id, tender_folder, bid_folder
                       FROM projects ORDER BY id'''):
    print(r)

print('\n===== users =====')
for r in cur.execute('SELECT id, username, real_name, role FROM users ORDER BY id'):
    print(r)

print('\n===== storage_zones =====')
for r in cur.execute('''SELECT id, name, mode, webdav_url, webdav_port,
                              webdav_use_ssl, webdav_base_path, sub_path
                       FROM storage_zones ORDER BY id'''):
    print(r)
c.close()
