"""Phase 0.5a - list-files 全链路代码仿真

模拟:
1) project_id=4, folder_type='tender' 走 _resolve_target_dir_self_healing
2) 真实从 NAS PROPFIND 对 target_dir, 拿到 PROPFIND 响应 body
3) 喂给 _parse_profind, 看它:
   ① 解析出多少条目
   ② 异常路径是否被触发
4) 跟 list_files_webdav 全链路模拟
"""
import sqlite3, sys, os, json
sys.path.insert(0, r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend')
os.environ['PYTHONPATH'] = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend'

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import warnings
warnings.simplefilter('ignore', InsecureRequestWarning)

# 模拟前端传入
import requests
target_url = 'https://172.16.10.252:5006/opencalw-1/自营测试区/张林+自营换渠道存储+2026-09-04/招标资料'
cfg_zone = {
    'webdav_url': '172.16.10.252',
    'webdav_port': 5006,
    'webdav_use_ssl': True,
    'webdav_username': 'trae',
    'webdav_password': 'akwj210627',
    'webdav_base_path': '/opencalw-1/自营测试区',
}

# 1) 真实 PROPFIND
print('=== ① 真实 PROPFIND ===')
resp = requests.request('PROPFIND', target_url,
    headers={'Depth': '1'}, auth=('trae', 'akwj210627'), verify=False, timeout=20)
print(f'status={resp.status_code} body_len={len(resp.content)}')

# 存 body 喂 _parse_profind
body_bytes = resp.content

# 2) 让 _parse_profind 解析
print('\n=== ② 喂给 _parse_profind ===')
from app.services.webdav_client import _parse_profind, _request
from types import SimpleNamespace

cfg = SimpleNamespace(**cfg_zone)

# 模拟一个 resp-like 对象
class FakeResp:
    def __init__(self, code, content):
        self.status_code = code
        self.content = content
fake = FakeResp(resp.status_code, body_bytes)

try:
    ok, lst = _parse_profind(fake)
    print(f'ok={ok} count={len(lst)}')
    for item in lst:
        print('   ', item)
except Exception as e:
    print(f'CRASH: {type(e).__name__}: {e}')

# 3) 再去一次, 但确保 inside _parse_profind 会经过 is_collection 比较
print('\n=== ③ 模拟第二次（看 is_collection 分支） ===')
# 解析 PROPFIND body, 看 href 列表
import xml.etree.ElementTree as ET
ns = {'d': 'DAV:'}
root = ET.fromstring(body_bytes)
print('原始 href 列表:')
for response in root.findall('.//d:response', ns):
    href = response.find('d:href', ns)
    if href is None: continue
    import urllib.parse
    raw = href.text
    decoded = urllib.parse.unquote(raw or '')
    print(f'    raw={raw!r}')
    print(f'    decoded={decoded!r}')
    print()

# 4) _parse_profind 在第 317 行会问 folder_url 这个名字 (UnboundLocalError because not in scope)
print('\n=== ④ 模拟 folder_url 作用域 ===')
print(f'folder_url passed in: {target_url}')
print('call _parse_profind(fake) -- expected to either succeed or silently return (False, [])')
result = _parse_profind(fake)
print(f'returned: {result}')
