"""验证 normalize_full_url 的修复效果"""
import sys, os
sys.path.insert(0, r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend')
os.environ['PYTHONPATH'] = r'Z:\soft-RED\hermes\开发软件\渠道项目登记\backend'

from types import SimpleNamespace
from app.services.file_storage import normalize_full_url, _dedupe_path_in_full_url

cfg = SimpleNamespace(
    mode='webdav',
    webdav_url='172.16.10.252',
    webdav_port=5006,
    webdav_use_ssl=True,
    webdav_base_path='/opencalw-1/渠道测试区',
    webdav_username='trae',
    webdav_password='x',
    local_path=None,
    template='',
)

cases = [
    ('纯相对+已含base', 'opencalw-1/渠道测试区/张林+自营换渠道存储+2026-09-04/招标资料'),
    ('纯相对+不含base', '张林+自营换渠道存储+2026-09-04/招标资料'),
    ('完整URL双层base', 'https://172.16.10.252:5006/opencalw-1/渠道测试区/opencalw-1/渠道测试区/张林+自营换渠道存储+2026-09-04/招标资料'),
    ('完整URL单层base', 'https://172.16.10.252:5006/opencalw-1/渠道测试区/张林+自营换渠道存储+2026-09-04/招标资料'),
    ('相对 = base_path 单段', 'opencalw-1/渠道测试区'),
    ('完整URL其它zone双层', 'https://172.16.10.252:5006/opencalw-1/自营测试区/opencalw-1/自营测试区/foo/招标资料'),
]

for label, inp in cases:
    out = normalize_full_url(inp, cfg)
    print(f'--- {label} ---')
    print(f'  in : {inp}')
    print(f'  out: {out}')
    print()
