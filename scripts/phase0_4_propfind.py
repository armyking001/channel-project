"""Phase 0.4 - 对项目 ID=4 探针:
1) DB 原始 tender_folder / bid_folder
2) 调用后端 _resolve_target_dir_self_healing (本地函数)
3) 对①②URL 发 PROPFIND, 状态码 + 条目数
4) 对 NAS 已知正确路径发 PROPFIND
   - opencalw-1/自营测试区/张林+自营换渠道存储+2026-09-04/招标资料
"""
import sqlite3, sys, os
import requests
sys.path.insert(0, r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend')
os.environ['PYTHONPATH'] = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend'

from app.routers.file_storage import _resolve_target_dir_self_healing
from app.services.file_storage import normalize_full_url
from app.database import SessionLocal

def propfind(url, user='trae', pwd='akwj210627'):
    """WebDAV PROPFIND with Depth: 1"""
    r = requests.request('PROPFIND', url, headers={'Depth': '1'}, auth=(user, pwd), verify=False, timeout=20)
    print(f'    status={r.status_code} len={len(r.content)}')
    return r.status_code, r.content

import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

# DB dump before
conn = sqlite3.connect(r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend\data.db')
c = conn.cursor()
print('===== ① DB 原始 =====')
for r in c.execute('SELECT id, tender_folder, bid_folder FROM projects WHERE id=4'):
    print(r)

# ② 后端 _resolve_target_dir_self_healing 返回
db = SessionLocal()
target_t, _, src_t = _resolve_target_dir_self_healing(db, 4, 'tender', '招标资料')
target_b, _, src_b = _resolve_target_dir_self_healing(db, 4, 'bid', '投标文档')
print(f'\n===== ② _resolve_target_dir_self_healing 返回 =====')
print(f'  tender_folder = {target_t!r}  src={src_t}')
print(f'  bid_folder    = {target_b!r}  src={src_b}')

# DB dump after (看是否被自愈写回)
print('\n===== ③ DB 写回后（detection）=====')
for r in c.execute('SELECT id, tender_folder, bid_folder FROM projects WHERE id=4'):
    print(r)

# ④ PROPFIND 测
print('\n===== ④ PROPFIND 测试 =====')
for label, url in [
    ('DB-raw tender', 'https://172.16.10.252:5006/opencalw-1/自营测试区/张林+自营换渠道存储+2026-09-04/招标资料'),
    ('selfheal tender', target_t),
    ('selfheal bid', target_b),
    # 用不正确路径（系统管理员+项目）模拟错误渲染
    ('wrong-render (creator=admin)', 'https://172.16.10.252:5006/渠道资料/系统管理员+自营换渠道存储+2026-09-04/招标资料'),
    # 默认 zone (id=7)
    ('zone 7 base', 'https://172.16.10.252:5006/渠道资料/'),
]:
    print(f'  --- {label} ---')
    print(f'    url: {url}')
    try:
        propfind(url)
    except Exception as e:
        print(f'    ERR: {e}')

db.close()
conn.close()
