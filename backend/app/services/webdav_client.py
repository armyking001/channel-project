"""WebDAV 客户端封装 - 上传/下载/列表"""
import os
import posixpath
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _auth(config):
    """组装 BASIC 认证 tuple（username 为空时返回 None）"""
    if config.webdav_username:
        return (config.webdav_username or '', config.webdav_password or '')
    return None


def _request(method, url, config, timeout=10, extra_headers=None, depth='1'):
    """通用 WebDAV 请求（禁用 SSL 验证 + 超时）
    depth: PROPFIND 默认 Depth=1，避免触发 Synology 'PROPFIND requests with Depth: infinity are not allowed'
    """
    # 容错：把"汉字之间的 0x20 空格"重新编码为 %20
    # Synology WebDAV 真实目录名是 %20 编码的；数据库存的 URL 是带裸空格或无空格
    if url.startswith('http') and ' ' in url:
        import re as _re
        url = _re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1%20\2', url)
    # 容错：把 + 号编码为 %2B（避免被 URL 解析成空格）
    if url.startswith('http') and '+' in url:
        import re as _re
        # 只编码路径中的 +（不影响 query string）
        scheme_end = url.find('://') + 3
        path_start = url.find('/', scheme_end)
        if path_start > 0:
            scheme_netloc = url[:path_start]
            path_and_query = url[path_start:]
            # 分割 path 和 query
            query_idx = path_and_query.find('?')
            if query_idx > 0:
                path = path_and_query[:query_idx]
                query = path_and_query[query_idx:]
            else:
                path = path_and_query
                query = ''
            path = path.replace('+', '%2B')
            url = scheme_netloc + path + query
    headers = {'User-Agent': 'channel-project-storage/1.0'}
    if method.upper() == 'PROPFIND':
        headers['Depth'] = depth
    if extra_headers:
        headers.update(extra_headers)
    return requests.request(
        method, url,
        auth=_auth(config),
        headers=headers,
        timeout=timeout,
        verify=False,
    )


def _ensure_parent_dir(url: str, config, timeout: int = 15):
    """递归 MKCOL 创建父级目录（从根到文件父目录）
    例如 https://nas/dav/base/项目/招标资料/file.doc
    将依次 MKCOL: 项目 -> 招标资料
    """
    parsed = urllib.parse.urlparse(url)
    # 分段：去掉首段空字符串，去掉文件名
    parts = [p for p in parsed.path.split('/') if p]
    if len(parts) < 2:
        return True, '无需建目录'

    base_path = (config.webdav_base_path or '').strip('/')
    # 找出 base_path 在 parts 中的索引
    base_idx = 0
    if base_path:
        bp_parts = [p for p in base_path.split('/') if p]
        for i in range(min(len(bp_parts), len(parts))):
            if parts[i] != bp_parts[i]:
                base_idx = i
                break
        else:
            base_idx = len(bp_parts)

    scheme = parsed.scheme
    host = f'{scheme}://{parsed.netloc}'

    # 需要创建的目录段：从 base_idx 开始，到倒数第二个（排除文件名）
    to_create = parts[base_idx:-1]
    current_parts = parts[:base_idx]
    for seg in to_create:
        current_parts.append(seg)
        dir_url = host + '/' + '/'.join(current_parts)
        try:
            r = _request('PROPFIND', dir_url, config, timeout=timeout)
            if 200 <= r.status_code < 300:
                continue
            # 404 明确不存在；405/403/400 等其他错误可能是 Synology WebDAV 限制，
            # 不应阻塞上传 — 直接尝试 MKCOL
            r2 = _request('MKCOL', dir_url, config, timeout=timeout)
            if 200 <= r2.status_code < 300:
                continue
            # MKCOL 返回 405 通常表示目录已存在（Synology 行为）
            if r2.status_code in (405, 301, 302):
                # 视为已存在，继续
                continue
            return False, f'目录创建失败 {dir_url}: PROPFIND={r.status_code}, MKCOL={r2.status_code} {r2.text[:100]}'
        except Exception as e:
            return False, f'目录异常 {dir_url}: {e}'
    return True, '目录就绪'


def delete_file_webdav(config, target_url: str, timeout: int = 15) -> bool:
    """DELETE WebDAV 上的文件（返回 True/False）"""
    if not target_url.startswith('http'):
        return False
    try:
        resp = _request('DELETE', target_url, config, timeout=timeout)
        return 200 <= resp.status_code < 300 or resp.status_code in (404, 204)
    except Exception:
        return False


def upload_file(config, target_url: str, content: bytes, timeout: int = 30):
    """PUT 文件到 WebDAV（一次性 bytes）
    target_url: 完整 URL（含文件名）
    content: 文件二进制
    返回 (ok, msg)
    """
    if not target_url.startswith('http'):
        return False, f'非法 URL: {target_url}'
    try:
        # 先确保父目录存在
        ok, msg = _ensure_parent_dir(target_url, config, timeout=min(timeout, 15))
        if not ok:
            return False, f'父目录未就绪: {msg}'

        resp = requests.put(
            target_url,
            data=content,
            auth=_auth(config),
            headers={
                'User-Agent': 'channel-project-storage/1.0',
                'Content-Type': 'application/octet-stream',
            },
            timeout=timeout,
            verify=False,
        )
        if 200 <= resp.status_code < 300:
            return True, f'HTTP {resp.status_code}'
        if resp.status_code in (401, 403):
            return False, f'认证失败 HTTP {resp.status_code}'
        return False, f'HTTP {resp.status_code}: {resp.text[:200]}'
    except requests.exceptions.SSLError as e:
        return False, f'SSL 错误: {e}'
    except requests.exceptions.ConnectTimeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError as e:
        return False, f'连接失败: {e}'
    except Exception as e:
        return False, f'上传失败: {e}'


def _iter_chunks(file_obj, chunk_size: int = 1024 * 1024):
    """从文件对象逐 chunk 读取（生成器）

    - 支持普通 file 对象（read(n)）
    - 支持 FastAPI/Starlette UploadFile.file (SpooledTemporaryFile)
    - 支持 SpooledTemporaryFile 实际是 BytesIO / TemporaryFile 的情况
    """
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk


def upload_file_streaming(config, target_url: str, data_iter=None, file_obj=None, file_size: int = None,
                          timeout: int = 300, chunk_size: int = 1024 * 1024,
                          on_progress=None):
    """PUT 文件到 WebDAV (流式,内存恒定)
    三种调用方式(优先 data_iter,其次 file_obj):
      1. data_iter: 已构造好的 generator/iterator,逐 yield bytes
      2. file_obj: 有 read(n) 方法的文件对象（UploadFile.file / open(..., 'rb') / BytesIO）
    file_size: 文件总大小（用于 Content-Length; None 时使用 chunked transfer）
    on_progress: 可选回调 on_progress(bytes_sent, total_bytes) -> None
    返回 (ok, msg)

    优势：
    1. 内存占用恒定 ~chunk_size (默认 1MB),不一次性加载整个 600MB
    2. requests 内部使用 chunked transfer,网络中断时已发部分不算失败
    3. 配合 Content-Length 让 WebDAV 服务器 (如 Synology) 能提前分配空间
    """
    if not target_url.startswith('http'):
        return False, f'非法 URL: {target_url}'
    try:
        # 1) 先确保父目录存在
        ok, msg = _ensure_parent_dir(target_url, config, timeout=min(timeout, 15))
        if not ok:
            return False, f'父目录未就绪: {msg}'

        # 2) 构造 chunk generator,带进度回调
        def _gen():
            sent = 0
            total = file_size or 0
            if data_iter is not None:
                for chunk in data_iter:
                    if not chunk:
                        continue
                    sent += len(chunk)
                    if on_progress:
                        try:
                            on_progress(sent, total)
                        except Exception:
                            pass
                    yield chunk
            elif file_obj is not None:
                for chunk in _iter_chunks(file_obj, chunk_size):
                    sent += len(chunk)
                    if on_progress:
                        try:
                            on_progress(sent, total)
                        except Exception:
                            pass
                    yield chunk
            else:
                return  # 无数据源

        # 3) 发送 headers(可选 Content-Length 提升 NAS 兼容性)
        headers = {
            'User-Agent': 'channel-project-storage/1.0',
            'Content-Type': 'application/octet-stream',
        }
        if file_size:
            headers['Content-Length'] = str(file_size)
        else:
            headers['Transfer-Encoding'] = 'chunked'

        # 4) requests 实际以 chunked 形式 PUT（无需拼整文件）
        resp = requests.put(
            target_url,
            data=_gen(),
            auth=_auth(config),
            headers=headers,
            timeout=timeout,
            verify=False,
        )
        if 200 <= resp.status_code < 300:
            return True, f'HTTP {resp.status_code}'
        if resp.status_code in (401, 403):
            return False, f'认证失败 HTTP {resp.status_code}'
        return False, f'HTTP {resp.status_code}: {resp.text[:200]}'
    except requests.exceptions.SSLError as e:
        return False, f'SSL 错误: {e}'
    except requests.exceptions.ConnectTimeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError as e:
        return False, f'连接失败: {e}'
    except requests.exceptions.ReadTimeout:
        return False, f'读取超时(文件过大,网络慢)'
    except Exception as e:
        return False, f'上传失败: {e}'


def _space_variants_for_project(project_name: str, folder_url: str) -> list:
    """对 project_name / folder_url 生成多种"插入 1 个空格"的变体 URL。
    适用情况：数据库存的项目名是"无空格版"，但 Synology 实际目录是"含 1 空格版"（仅一处空格）。

    主要场景：项目名末尾含 "采购项目"，WebDAV 上真实目录是 "采 购项目"（"采"和"购"之间）。
    """
    if not folder_url:
        return [folder_url]

    alts = []

    # 1. 精准替换：把 URL 中所有 "采购项目" 替换成 "采 购项目"（仅一次即可）
    if '采购项目' in folder_url and '采 购项目' not in folder_url:
        alt = folder_url.replace('采购项目', '采 购项目')
        if alt != folder_url and alt not in alts:
            alts.append(alt)

    # 2. 通用：基于 project_name 中每个 4+ 汉字 run，在每个位置插入 1 个空格
    if project_name:
        import re as _re3
        han_runs = _re3.findall(r'[\u4e00-\u9fff]{4,}', project_name)
        for run in han_runs:
            for i in range(1, len(run)):
                variant_run = run[:i] + ' ' + run[i:]
                alt = folder_url.replace(run, variant_run, 1)
                if alt != folder_url and alt not in alts:
                    alts.append(alt)

    return alts


def _parse_profind(resp):
    """解析 PROPFIND 的 XML 响应 -> (True, file_list)"""
    try:
        ns = {'d': 'DAV:'}
        root = ET.fromstring(resp.content)
        files = []
        for response in root.findall('.//d:response', ns):
            href = response.find('d:href', ns)
            if href is None:
                continue
            href_text = href.text or ''
            decoded_path = urllib.parse.unquote(href_text)
            resourcetype = response.find('.//d:resourcetype', ns)
            is_collection = False
            if resourcetype is not None and resourcetype.find('d:collection', ns) is not None:
                is_collection = True
            if is_collection:
                continue
            name = posixpath.basename(decoded_path.rstrip('/'))
            if not name:
                continue
            size = 0
            size_elem = response.find('.//d:getcontentlength', ns)
            if size_elem is not None and size_elem.text:
                try: size = int(size_elem.text)
                except (ValueError, TypeError): pass
            mtime = int(time.time())
            mtime_elem = response.find('.//d:getlastmodified', ns)
            if mtime_elem is not None and mtime_elem.text:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(mtime_elem.text)
                    mtime = int(dt.timestamp())
                except Exception: pass
            files.append({'name': name, 'path': decoded_path, 'size': size, 'mtime': mtime})
        return True, sorted(files, key=lambda x: x['name'])
    except Exception:
        return False, []


def list_files_webdav(config, folder_url: str, timeout: int = 15, project_name_hint: str = None):
    """通过 PROPFIND 列出 WebDAV 目录下的文件
    folder_url: 目录 URL（如 https://nas/dav/base/项目/招标资料）
    project_name_hint: 项目名（用于在 404 时生成正确的"含空格 URL"变体）
    返回 (ok, file_list)
    file_list 每项: {name, path, size, mtime}
    """
    if not folder_url.startswith('http'):
        return False, []
    try:
        headers = {
            'User-Agent': 'channel-project-storage/1.0',
            'Depth': '1',
        }
        resp = _request('PROPFIND', folder_url, config, timeout=timeout, extra_headers=headers)
        if not (200 <= resp.status_code < 300):
            # 404 容错：尝试给 project_name_hint 加 1 个空格（数据库存的是无空格版，但真实目录是带空格的）
            alts = _space_variants_for_project(project_name_hint, folder_url)
            for alt in alts:
                if alt == folder_url:
                    continue
                resp2 = _request('PROPFIND', alt, config, timeout=timeout, extra_headers=headers)
                if 200 <= resp2.status_code < 300:
                    return _parse_profind(resp2)
        return _parse_profind(resp)
    except requests.exceptions.SSLError as e:
        return False, []
    except requests.exceptions.ConnectTimeout:
        return False, []
    except requests.exceptions.ConnectionError:
        return False, []
    except Exception:
        return False, []


def probe_dir_exists(config, dir_url: str, timeout: int = 4) -> bool:
    """PROPFIND Depth:0 探测目录是否存在（不开文件列表，开销小）

    用法：升级/迁移后，DB 里的 tender_folder/bid_folder 可能过时，
    用本函数在 WebDAV 上探测多种候选命名，找到第一个存在的就当事实真目录。
    """
    if not dir_url or not dir_url.startswith('http'):
        return False
    try:
        headers = {
            'User-Agent': 'channel-project-storage/1.0',
            'Depth': '0',
        }
        resp = _request('PROPFIND', dir_url, config, timeout=timeout, extra_headers=headers)
        return 200 <= resp.status_code < 300
    except requests.exceptions.SSLError:
        return False
    except requests.exceptions.ConnectTimeout:
        return False
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False
