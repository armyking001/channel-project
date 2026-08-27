"""表单文件存储服务 — 基于 StorageZone 路由到不同区域

每个表单模板可关联一个 StorageZone（默认使用第一个可用区域）。
实例化时根据 zone.sub_path + 模板路径模板自动生成文件夹路径。
"""
import os
import re
import datetime
from typing import Tuple, Optional, List

from sqlalchemy.orm import Session

from app.models import (
    FileStorageConfig, StorageMode, FormTemplate, FormInstance, User, StorageZone,
)
from app.services.file_storage import (
    render_project_root, render_subfolder, render_zone_root,
    sanitize_path_segment, ensure_local_folders, webdav_request,
)


def _get_default_zone(db: Session) -> Optional[StorageZone]:
    """获取默认存储区域（按 sort_order, id 取第一个启用的）"""
    return db.query(StorageZone).filter(StorageZone.is_active == True)\
        .order_by(StorageZone.sort_order, StorageZone.id).first()


def _get_zone(db: Session, zone_id: Optional[int]) -> Optional[StorageZone]:
    """按 ID 获取区域；无 ID 返回默认区域"""
    if zone_id:
        z = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
        if z:
            return z
    return _get_default_zone(db)


def compute_form_folders(
    db: Session,
    template_id: int,
    instance_id: int,
    username: str,
    real_name: str,
    project_name: str,
    responsible_sales: Optional[str] = None,
    created_at: Optional[datetime.datetime] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """计算并回写 FormInstance 的 tender_folder / bid_folder

    优先级：
      1. FormTemplate.storage_zone_id
      2. 系统默认 StorageZone

    如果实例已有 tender_folder / bid_folder（create_instance 时已写入），则复用，不再重建。
    """
    instance = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not instance:
        return None, None

    # 已有 tender_folder / bid_folder 时直接复用（避免 init_form_folders 误覆盖）
    if instance.tender_folder and instance.bid_folder:
        # 但仍确保子目录已存在（幂等 MKCOL，PROPFIND 已存在时直接跳过）
        template = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
        if template:
            zone = _get_zone(db, template.storage_zone_id)
            if zone:
                _ensure_form_directories_zone(zone, instance.tender_folder, instance.bid_folder)
            else:
                cfg = _get_cfg(db)
                _ensure_form_directories(cfg, instance.tender_folder, instance.bid_folder)
        return instance.tender_folder, instance.bid_folder

    template = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not template:
        return None, None

    # 解析存储区域
    zone_id = template.storage_zone_id
    zone = _get_zone(db, zone_id)

    created_at = created_at or instance.created_at or datetime.datetime.now()
    # 责任销售优先（决定文件夹命名）
    sales_name = (responsible_sales or '').strip() or real_name
    if zone:
        root = render_zone_root(zone, username, real_name, project_name, sales_name, created_at)
    else:
        # 兜底：用旧 FileStorageConfig
        cfg = _get_cfg(db)
        root = render_project_root(cfg, username, real_name, project_name, sales_name, created_at)

    tender_dir = render_subfolder(root, '招标资料')
    bid_dir = render_subfolder(root, '投标文档')

    instance.tender_folder = tender_dir
    instance.bid_folder = bid_dir
    db.add(instance)
    db.commit()
    db.refresh(instance)

    if zone:
        _ensure_form_directories_zone(zone, tender_dir, bid_dir)
    else:
        cfg = _get_cfg(db)
        _ensure_form_directories(cfg, tender_dir, bid_dir)
    return tender_dir, bid_dir


def _get_cfg(db: Session) -> FileStorageConfig:
    cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    if not cfg:
        cfg = FileStorageConfig(id=1, mode=StorageMode.local)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _ensure_form_directories(cfg: FileStorageConfig, tender_dir: str, bid_dir: str):
    """确保表单的两个子目录已创建（基于 FileStorageConfig）"""
    if cfg.mode == StorageMode.local:
        ensure_local_folders([tender_dir, bid_dir])
    else:
        for label, dir_path in [('招标资料', tender_dir), ('投标文档', bid_dir)]:
            ok, msg = webdav_request(
                'MKCOL', dir_path,
                cfg.webdav_username, cfg.webdav_password,
            )
            if not ok and '405' not in msg:
                pass


def _ensure_form_directories_zone(zone: StorageZone, tender_dir: str, bid_dir: str):
    """确保表单的两个子目录已创建（基于 StorageZone）"""
    import logging
    log = logging.getLogger("forms")
    if zone.mode == StorageMode.local:
        ensure_local_folders([tender_dir, bid_dir])
        return
    # WebDAV: 先 MKCOL 父目录，再 MKCOL 子目录
    # tender_dir 形如 https://host/path/账号+项目+日期/招标资料
    # 父目录：去掉最后一段
    tender_parent = '/'.join(tender_dir.split('/')[:-1])
    bid_parent = '/'.join(bid_dir.split('/')[:-1])

    for parent in [tender_parent, bid_parent]:
        ok, msg = webdav_request(
            'MKCOL', parent,
            zone.webdav_username or '', zone.webdav_password or '',
        )
        log.warning(f"[MKCOL parent] {parent} -> ok={ok} msg={msg[:80]}")

    for label, dir_path in [('招标资料', tender_dir), ('投标文档', bid_dir)]:
        ok, msg = webdav_request(
            'MKCOL', dir_path,
            zone.webdav_username or '', zone.webdav_password or '',
        )
        log.warning(f"[MKCOL child] {label} {dir_path} -> ok={ok} msg={msg[:80]}")


def _zone_webdav_prefix(zone: StorageZone) -> str:
    """返回 zone 在 WebDAV 模式下的前缀 URL（不含子路径、不含项目目录）

    例：https://host:port/dav/base
    """
    if zone.mode != StorageMode.webdav:
        return ''
    host = (zone.webdav_url or '').strip()
    scheme = 'https' if zone.webdav_use_ssl else 'http'
    if host.startswith('http://'):
        host = host[len('http://'):]; scheme = 'http'
    elif host.startswith('https://'):
        host = host[len('https://'):]; scheme = 'https'
    host = host.rstrip('/')
    host_part = f'{scheme}://{host}'
    if zone.webdav_port:
        host_part += f':{zone.webdav_port}'
    base_path = (zone.webdav_base_path or '').strip('/')
    parts = [host_part]
    if base_path:
        parts.append(base_path)
    sub_path = (zone.sub_path or '').strip('/').strip()
    if sub_path:
        parts.append(sub_path)
    return '/'.join(parts).rstrip('/')


def _candidate_project_folders(
    zone: StorageZone,
    owner: User,
    project_name: str,
    responsible_sales: Optional[str],
    created_at: Optional[datetime.datetime],
) -> List[str]:
    """生成多个候选"项目根目录"（不含子目录招标资料/投标文档），按可能性排序

    用法：升级/迁移后，DB 里的 tender_folder/bid_folder 可能过时；
    依次探测这些候选名 + 候选子目录名组合，第一个 PROPFIND 200 的就是事实真目录。
    """
    sales = (responsible_sales or '').strip() or (owner.real_name or '').strip() or (owner.username or '').strip() or 'unknown'
    sales = sanitize_path_segment(sales)
    real = sanitize_path_segment((owner.real_name or '').strip() or (owner.username or '').strip() or 'unknown')
    user = sanitize_path_segment((owner.username or '').strip() or (owner.real_name or '').strip() or 'unknown')
    proj = sanitize_path_segment(project_name or 'unnamed')

    date_str = created_at.strftime('%Y-%m-%d') if created_at else ''

    # 按可能性从高到低
    candidates = []
    seen = set()
    def add(tpl: str):
        if tpl and tpl not in seen:
            seen.add(tpl)
            candidates.append(tpl)

    if sales and proj and date_str:
        add(f'{sales}+{proj}+{date_str}')         # 主模板（截图规格）
    if real and proj and date_str:
        add(f'{real}+{proj}+{date_str}')           # 兼容老版本
    if user and proj and date_str:
        add(f'{user}+{proj}+{date_str}')
    if sales and proj:
        add(f'{sales}+{proj}')
    if real and proj:
        add(f'{real}+{proj}')
    if proj and date_str:
        add(f'{proj}+{date_str}')
    if proj:
        add(proj)

    return candidates


def _discover_form_folders(
    db: Session,
    instance: FormInstance,
    zone: StorageZone,
    owner: User,
    project_name: str,
) -> Tuple[Optional[str], Optional[str], str]:
    """在 WebDAV 上探测已有的项目目录

    返回 (tender_dir, bid_dir, source)；都不存在返回 (None, None, 'not_found')

    策略：
      1. 取 instance.data 里的 responsible_sales（如果有的话）
      2. 生成多种候选项目根目录名
      3. 候选子目录名：['招标资料','招标文件','投标文档']
      4. PROPFIND Depth:0 探测每个候选
      5. 找到后把 tender_folder/bid_folder 回写 DB

    本地模式直接用 render_zone_root 算路径，不做探测。
    """
    # 本地模式：直接算路径（不走探测）
    if zone.mode == StorageMode.local:
        import json as _json
        try:
            data = _json.loads(instance.data or '{}')
        except Exception:
            data = {}
        responsible = (
            data.get('responsible_sales')
            or data.get('responsible_sales_name')
            or data.get('sales_name')
            or owner.real_name
        )
        created_at = instance.created_at
        root = render_zone_root(zone, owner.username, owner.real_name, project_name, responsible, created_at)
        tender_dir = render_subfolder(root, '招标资料')
        bid_dir = render_subfolder(root, '投标文档')
        return tender_dir, bid_dir, 'local'

    # WebDAV 模式：探测
    from app.services.webdav_client import probe_dir_exists
    import json as _json
    try:
        data = _json.loads(instance.data or '{}')
    except Exception:
        data = {}
    responsible = (
        data.get('responsible_sales')
        or data.get('responsible_sales_name')
        or data.get('sales_name')
        or owner.real_name
    )
    created_at = instance.created_at

    candidates = _candidate_project_folders(zone, owner, project_name, responsible, created_at)
    if not candidates:
        return None, None, 'no_candidates'

    # 把 zone 临时塞进一个简单包装，让 probe_dir_exists 能用其凭据
    class _ZoneCfgShim:
        def __init__(self, z: StorageZone):
            self.webdav_username = z.webdav_username
            self.webdav_password = z.webdav_password
            self.webdav_use_ssl = z.webdav_use_ssl
    cfg = _ZoneCfgShim(zone)

    prefix = _zone_webdav_prefix(zone)
    sub_dir_candidates = {
        'tender': ['招标资料', '招标文件', 'tender'],
        'bid':    ['投标文档', '投标文件', 'bid'],
    }

    tender_dir = None
    bid_dir = None
    matched_template = None

    # 优先尝试 DB 里已存的（如果存在）
    if instance.tender_folder or instance.bid_folder:
        if instance.tender_folder and probe_dir_exists(cfg, instance.tender_folder):
            tender_dir = instance.tender_folder
        if instance.bid_folder and probe_dir_exists(cfg, instance.bid_folder):
            bid_dir = instance.bid_folder
        # 都找到了直接返回
        if tender_dir and bid_dir:
            return tender_dir, bid_dir, 'db_validated'
        # 找到了其中一个，从那里取前缀去推导另一个
        if tender_dir or bid_dir:
            anchor = tender_dir or bid_dir
            # 父目录 = .../<project_template>
            anchor_prefix = '/'.join(anchor.split('/')[:-1])
            # 试探其它子目录名
            for s in sub_dir_candidates[folder_type_silent := ('tender' if not tender_dir else 'bid')]:
                cand = anchor_prefix + '/' + s
                if probe_dir_exists(cfg, cand):
                    if not tender_dir:
                        tender_dir = cand
                    elif not bid_dir:
                        bid_dir = cand
            if tender_dir and bid_dir:
                return tender_dir, bid_dir, 'db_partial'

    # 通用探测：每个候选项目目录名 × 每种子目录名
    for proj_folder in candidates:
        for sub in sub_dir_candidates['tender']:
            cand_t = f'{prefix}/{proj_folder}/{sub}'
            if probe_dir_exists(cfg, cand_t):
                tender_dir = cand_t
                bid_sub = next((s for s in sub_dir_candidates['bid'] if s != sub), '投标文档')
                bid_cand = f'{prefix}/{proj_folder}/{bid_sub}'
                if probe_dir_exists(cfg, bid_cand):
                    bid_dir = bid_cand
                else:
                    # 探测其它 bid 子目录名
                    for alt in sub_dir_candidates['bid']:
                        if alt == sub:
                            continue
                        cand = f'{prefix}/{proj_folder}/{alt}'
                        if probe_dir_exists(cfg, cand):
                            bid_dir = cand
                            break
                matched_template = proj_folder
                break
        if tender_dir:
            break
        # 如果 tender 没找到但 bid 找到了（老系统可能只有投标），也认账
        for sub in sub_dir_candidates['bid']:
            cand_b = f'{prefix}/{proj_folder}/{sub}'
            if probe_dir_exists(cfg, cand_b):
                bid_dir = cand_b
                matched_template = proj_folder
                break
        if bid_dir and not tender_dir:
            # 同步探测 tender
            for sub in sub_dir_candidates['tender']:
                cand_t = f'{prefix}/{proj_folder}/{sub}'
                if probe_dir_exists(cfg, cand_t):
                    tender_dir = cand_t
                    break

    if not tender_dir and not bid_dir:
        return None, None, 'not_found'

    return tender_dir, bid_dir, f'discovered:{matched_template or "?"}'


def resolve_form_folder(
    db: Session,
    instance_id: int,
    folder_type: str,
) -> Tuple[str, str, str]:
    """解析 FormInstance 的 folder 路径

    返回 (target_dir, project_name, status)
    status 取值：
      - 'db'                DB 里存的就是当前真目录
      - 'db_validated'      DB 里存的路径，探测 WebDAV 后确认存在
      - 'db_partial'        DB 字段部分对、部分靠推断
      - 'local'             本地模式，按模板算
      - 'discovered:xxx'    WebDAV 上探测到了 xxx 模板对应的目录
      - 'recovered'         DB 字段空，用当前模板算并写回（仅当 WebDAV 探测失败/不可用）
      - 'not_found'         WebDAV 上找不到
      - 'missing'           instance 不存在
    """
    instance = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not instance:
        return '', '', 'missing'

    target_dir = (instance.tender_folder if folder_type == 'tender' else instance.bid_folder) or ''
    project_name = ''
    import json as _json
    try:
        data = _json.loads(instance.data or '{}')
    except Exception:
        data = {}
    project_name = data.get('project_name') or data.get('name') or f'表单{instance.id}'

    if target_dir:
        # DB 里有路径就先用 DB 里的（兼容历史数据 + 减少探测次数）
        # 但允许 _discover_form_folders 在探测时自动修正
        # 这里直接 return，把探测留给未来的自愈流程
        return target_dir, str(instance.id), 'db'

    # DB 字段为空 → 自愈：从 data 重建 + 在 WebDAV 上探测
    owner = db.query(User).filter(User.id == instance.created_by).first()
    if not owner:
        return '', project_name, 'missing'

    template = db.query(FormTemplate).filter(FormTemplate.id == instance.template_id).first()
    if not template:
        return '', project_name, 'missing'

    zone = _get_zone(db, template.storage_zone_id)
    if not zone:
        # 兜底：旧 FileStorageConfig
        cfg = _get_cfg(db)
        if cfg.mode == StorageMode.local:
            root = render_project_root(cfg, owner.username, owner.real_name, project_name, owner.real_name, instance.created_at)
            tender_dir = render_subfolder(root, '招标资料')
            bid_dir = render_subfolder(root, '投标文档')
            instance.tender_folder = tender_dir
            instance.bid_folder = bid_dir
            db.add(instance)
            db.commit()
            db.refresh(instance)
            return tender_dir if folder_type == 'tender' else bid_dir, project_name, 'recovered'
        else:
            return '', project_name, 'missing'

    tender_dir, bid_dir, source = _discover_form_folders(
        db, instance, zone, owner, project_name,
    )

    if tender_dir or bid_dir:
        # 写回 DB（即使只有一边找到也写，下次直接命中）
        if instance.tender_folder != tender_dir:
            instance.tender_folder = tender_dir
        if instance.bid_folder != bid_dir:
            instance.bid_folder = bid_dir
        if instance.storage_zone_id != zone.id:
            instance.storage_zone_id = zone.id
        db.add(instance)
        db.commit()
        db.refresh(instance)
        chosen = tender_dir if folder_type == 'tender' else bid_dir
        if chosen:
            return chosen, project_name, source
        # 当前 folder_type 没找到，但另一个找到了——回退到另一边的目录
        fallback = tender_dir or bid_dir
        return fallback, project_name, source

    # WebDAV 上找不到，回退到当前模板计算（不写 DB，避免污染）
    root = render_zone_root(zone, owner.username, owner.real_name, project_name, owner.real_name, instance.created_at)
    tender_dir = render_subfolder(root, '招标资料')
    bid_dir = render_subfolder(root, '投标文档')
    chosen = tender_dir if folder_type == 'tender' else bid_dir
    return chosen, project_name, 'not_found'