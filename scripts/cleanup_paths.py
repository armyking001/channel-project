"""清理 DB 里所有项目的 tender_folder / bid_folder 脏数据

策略:
  对每个项目, 用其对应的 StorageZone 构造 cfg, 调 normalize_full_url()
  把结果回写 DB。

用法:
  cd backend
  python ..\scripts\cleanup_paths.py        # 实际写入
  python ..\scripts\cleanup_paths.py --dry  # 只打印不写入
"""
import sys, os, sqlite3, argparse
sys.path.insert(0, r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend')
os.environ['PYTHONPATH'] = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend'

from types import SimpleNamespace
from app.services.file_storage import normalize_full_url


DB_PATH = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\data.db'


def _zone_to_cfg(zone_row):
    """StorageZone ORM 一行 → normalize_full_url 用的 cfg SimpleNamespace."""
    return SimpleNamespace(
        mode=zone_row['mode'] or 'webdav',
        webdav_url=zone_row['webdav_url'] or '',
        webdav_port=zone_row['webdav_port'],
        webdav_use_ssl=bool(zone_row['webdav_use_ssl']) if zone_row['webdav_use_ssl'] is not None else True,
        webdav_base_path=zone_row['webdav_base_path'] or '',
        webdav_username=zone_row['webdav_username'] or '',
        webdav_password=zone_row['webdav_password'] or '',
        local_path=zone_row['local_path'],
        template='',
    )


def main(dry: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 缓存 zones
    zones = {}
    for r in cur.execute('SELECT * FROM storage_zones'):
        zones[r['id']] = dict(r)

    changed = 0
    unchanged = 0
    skipped = 0
    for r in cur.execute('SELECT id, project_name, storage_zone_id, tender_folder, bid_folder FROM projects ORDER BY id'):
        pid = r['id']
        zid = r['storage_zone_id']
        zone = zones.get(zid) if zid else None
        if zone is None:
            print(f'  [skip] project_id={pid} (storage_zone_id={zid} 不存在)')
            skipped += 1
            continue

        cfg = _zone_to_cfg(zone)
        new_t = normalize_full_url(r['tender_folder'] or '', cfg) if r['tender_folder'] else r['tender_folder']
        new_b = normalize_full_url(r['bid_folder'] or '', cfg) if r['bid_folder'] else r['bid_folder']

        old_t, old_b = r['tender_folder'], r['bid_folder']
        new_t = new_t or old_t
        new_b = new_b or old_b

        if new_t != old_t or new_b != old_b:
            changed += 1
            print(f'  [fix] project_id={pid} {r["project_name"]}')
            print(f'    zone=#{zid} {zone["name"]} base_path={zone["webdav_base_path"]}')
            print(f'    tender_folder:')
            print(f'      before: {old_t}')
            print(f'      after : {new_t}')
            print(f'    bid_folder:')
            print(f'      before: {old_b}')
            print(f'      after : {new_b}')
            if not dry:
                cur.execute('UPDATE projects SET tender_folder=?, bid_folder=? WHERE id=?',
                            (new_t, new_b, pid))
        else:
            unchanged += 1

    if not dry:
        conn.commit()
    conn.close()

    print(f'\nSummary: changed={changed} unchanged={unchanged} skipped={skipped}{" (DRY RUN)" if dry else ""}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dry', action='store_true', help='只打印，不写入')
    args = p.parse_args()
    main(dry=args.dry)
