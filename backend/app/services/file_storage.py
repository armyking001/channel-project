"""文件存储服务：本地 + WebDAV 双模式
- 单例配置 (id=1)
- 模板渲染: {real_name}+{project_name}+{date}  (YYYY-MM-DD)
- 建项目时自动建子文件夹: 项目目录/招标资料 + 项目目录/投标文档
"""
import os
import re
import datetime
from typing import Tuple, Dict, Optional

import requests
from sqlalchemy.orm import Session

from app.models import FileStorageConfig, StorageMode


# ----- 工具：清理文件名 -----
def _sanitize(name: str) -> str:
    """去除文件系统非法字符"""
    if not name:
        return 'unnamed'
    # Windows 非法字符 + 路径分隔符
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    s = s.strip('. ').strip() or 'unnamed'
    return s[:80]  # 限制长度


# 别名：暴露给 router 使用
sanitize_path_segment = _sanitize


# ----- 工具：模板渲染 -----
def render_base_folder(config: FileStorageConfig, username: str, real_name: str,
                       project_name: str,
                       created_at: Optional[datetime.datetime] = None) -> str:
    """根据模板渲染项目根目录名（不含 mode 前缀）
    默认模板: {real_name}+{project_name}+{date}  — 姓名+项目名称+项目建立日期
    同时支持 {username} 和 {real_name} 变量
    """
    created_at = created_at or datetime.datetime.now()
    tpl = config.template or '{real_name}+{project_name}+{date}'
    return tpl.format(
        username=_sanitize(username),
        real_name=_sanitize(real_name),
        project_name=_sanitize(project_name),
        date=created_at.strftime('%Y-%m-%d'),
    )


# ----- 工具：根据 mode 返回完整路径（不含 tender/bid 子目录） -----
def render_project_root(config: FileStorageConfig, username: str, real_name: str,
                        project_name: str,
                        created_at: Optional[datetime.datetime] = None) -> str:
    """返回完整根目录：local -> 绝对路径, webdav -> URL 字符串"""
    folder = render_base_folder(config, username, real_name, project_name, created_at)
    if config.mode == StorageMode.local:
        base = (config.local_path or '').rstrip('\\/') or '.'
        return os.path.join(base, folder).replace('/', os.sep)
    # webdav: 拼 scheme://host[:port] + base_path + folder
    host = (config.webdav_url or '').strip()
    scheme = 'https' if getattr(config, 'webdav_use_ssl', True) else 'http'
    # 若用户填了带 scheme 的 URL，去掉 scheme 后我们重新加（避免重复）
    if host.startswith('http://'):
        host = host[len('http://'):]
        scheme = 'http'
    elif host.startswith('https://'):
        host = host[len('https://'):]
        scheme = 'https'
    host = host.rstrip('/')
    port = getattr(config, 'webdav_port', None)
    host_part = f'{scheme}://{host}'
    if port:
        host_part += f':{port}'
    base_path = (config.webdav_base_path or '').strip('/')
    parts = [host_part]
    if base_path:
        parts.append(base_path)
    parts.append(folder)
    return '/'.join(parts)


def render_subfolder(root: str, sub: str) -> str:
    """根目录 + 子目录（本地用系统分隔符；WebDAV 用 /）"""
    if root.startswith('http://') or root.startswith('https://'):
        return root.rstrip('/') + '/' + _sanitize(sub)
    return os.path.join(root, sub).replace('/', os.sep)


# ----- 模式：local -----
def ensure_local_folders(paths: list) -> Tuple[bool, str]:
    """本地模式：递归创建目录"""
    try:
        for p in paths:
            os.makedirs(p, exist_ok=True)
        return True, '本地目录已就绪'
    except Exception as e:
        return False, f'本地目录创建失败: {e}'


# ----- 模式：webdav -----
def webdav_request(method: str, url: str, username: str, password: str,
                   timeout: int = 10, depth: str = '1') -> Tuple[bool, str]:
    """WebDAV HTTP 请求（BASIC auth）
    返回 (成功, 消息)
    注意：NAS 内部署通常使用自签名证书，禁用 SSL 验证以提高兼容性
    depth: PROPFIND 的 Depth 头，Synology DSM 根目录不允许 infinity，统一使用 '1'
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        headers = {'User-Agent': 'channel-project-storage/1.0'}
        if method.upper() == 'PROPFIND':
            headers['Depth'] = depth
        resp = requests.request(
            method, url,
            auth=(username, password) if username else None,
            headers=headers,
            timeout=timeout,
            verify=False,
        )
        if 200 <= resp.status_code < 300:
            return True, f'HTTP {resp.status_code}'
        if resp.status_code in (401, 403):
            return False, f'认证失败 HTTP {resp.status_code}: {resp.text[:200]}'
        return False, f'HTTP {resp.status_code}: {resp.text[:200]}'
    except requests.exceptions.SSLError as e:
        return False, f'SSL 错误: {e}'
    except requests.exceptions.ConnectTimeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError as e:
        return False, f'连接失败: {e}'
    except Exception as e:
        return False, f'请求失败: {e}'


def ensure_webdav_folders(root_url: str, subfolders: list,
                          username: str, password: str) -> Tuple[bool, str]:
    """WebDAV 模式：递归 MKCOL 建目录
    root_url: 不含子目录的基础 URL（如 https://nas/dav/项目根目录）
    subfolders: ['招标资料', '投标文档']
    """
    # 先测根目录
    ok, msg = webdav_request('PROPFIND', root_url, username, password)
    if not ok:
        # 根目录可能不存在，尝试 MKCOL
        ok2, msg2 = webdav_request('MKCOL', root_url, username, password)
        if not ok2:
            return False, f'根目录不可访问且创建失败: {msg2}'

    created = []
    for sub in subfolders:
        sub_url = root_url.rstrip('/') + '/' + _sanitize(sub)
        ok, msg = webdav_request('PROPFIND', sub_url, username, password)
        if ok:
            created.append(f'{sub}(已存在)')
            continue
        ok, msg = webdav_request('MKCOL', sub_url, username, password)
        if ok:
            created.append(f'{sub}(新建)')
        else:
            return False, f'子目录 {sub} 创建失败: {msg}'
    return True, 'WebDAV 目录就绪: ' + ', '.join(created)


# ----- 入口：根据配置建项目目录（统一接口） -----
def create_project_folders(db: Session, config: FileStorageConfig,
                           username: str, real_name: str, project_name: str) -> Dict[str, str]:
    """根据配置自动建项目目录，返回 tender_folder / bid_folder 绝对路径
    文件夹名 = 模板渲染结果（支持 {username} 和 {real_name}）
    """
    root = render_project_root(config, username, real_name, project_name)
    tender = render_subfolder(root, '招标资料')
    bid = render_subfolder(root, '投标文档')

    if config.mode == StorageMode.local:
        ok, msg = ensure_local_folders([tender, bid])
    else:
        ok, msg = ensure_webdav_folders(
            root, ['招标资料', '投标文档'],
            config.webdav_username or '', config.webdav_password or ''
        )

    if not ok:
        raise RuntimeError(f'项目目录创建失败: {msg}')

    return {
        'base_folder': root,
        'tender_folder': tender,
        'bid_folder': bid,
        'message': msg,
    }


# ----- 入口：测试配置连通性 -----
def test_connection(config: FileStorageConfig) -> Tuple[bool, str]:
    """测试 storage 是否可达"""
    if config.mode == StorageMode.local:
        p = (config.local_path or '').strip()
        if not p:
            return False, '本地路径未配置'
        try:
            os.makedirs(p, exist_ok=True)
            test_file = os.path.join(p, '.storage_test')
            with open(test_file, 'w') as f:
                f.write('ok')
            os.remove(test_file)
            return True, f'本地路径可写: {p}'
        except Exception as e:
            return False, f'本地路径不可写: {e}'
    else:
        host = (config.webdav_url or '').strip()
        if not host:
            return False, 'WebDAV URL 未配置'
        scheme = 'https' if getattr(config, 'webdav_use_ssl', True) else 'http'
        if host.startswith('http://'):
            host = host[len('http://'):]
            scheme = 'http'
        elif host.startswith('https://'):
            host = host[len('https://'):]
            scheme = 'https'
        host = host.rstrip('/')
        port = getattr(config, 'webdav_port', None)
        url = f'{scheme}://{host}'
        if port:
            url += f':{port}'
        # 测根 + 测 base_path
        ok, msg = webdav_request(
            'PROPFIND', url,
            config.webdav_username or '', config.webdav_password or ''
        )
        if not ok:
            return False, f'WebDAV 根不可达: {msg}'
        bp = (config.webdav_base_path or '').strip('/')
        if bp:
            bp_url = url + '/' + bp
            ok2, msg2 = webdav_request(
                'PROPFIND', bp_url,
                config.webdav_username or '', config.webdav_password or ''
            )
            if not ok2:
                # 尝试 MKCOL
                ok3, msg3 = webdav_request(
                    'MKCOL', bp_url,
                    config.webdav_username or '', config.webdav_password or ''
                )
                if not ok3:
                    return False, f'base_path 不可达且无法创建: {msg3}'
        return True, f'WebDAV 可达: {url}'