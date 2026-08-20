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


def resolve_form_folder(
    db: Session,
    instance_id: int,
    folder_type: str,
) -> Tuple[str, str, str]:
    """解析 FormInstance 的 folder 路径

    返回 (target_dir, project_name, status)
    """
    instance = db.query(FormInstance).filter(FormInstance.id == instance_id).first()
    if not instance:
        return '', '', 'missing'

    target_dir = (instance.tender_folder if folder_type == 'tender' else instance.bid_folder) or ''
    if target_dir:
        return target_dir, str(instance.id), 'db'

    # 自修复：从 data 中提取 project_name 重建
    import json
    try:
        data = json.loads(instance.data or '{}')
    except Exception:
        data = {}

    project_name = data.get('project_name') or data.get('name') or f'表单{instance.id}'
    owner = db.query(User).filter(User.id == instance.created_by).first()
    if not owner:
        return '', project_name, 'missing'

    template = db.query(FormTemplate).filter(FormTemplate.id == instance.template_id).first()
    if not template:
        return '', project_name, 'missing'

    zone = _get_zone(db, template.storage_zone_id)
    if zone:
        root = render_zone_root(zone, owner.username, owner.real_name, project_name, owner.real_name, instance.created_at)
        _ensure_form_directories_zone(zone, render_subfolder(root, '招标资料'), render_subfolder(root, '投标文档'))
    else:
        cfg = _get_cfg(db)
        root = render_project_root(cfg, owner.username, owner.real_name, project_name, owner.real_name, instance.created_at)
        _ensure_form_directories(cfg, render_subfolder(root, '招标资料'), render_subfolder(root, '投标文档'))

    tender_dir = render_subfolder(root, '招标资料')
    bid_dir = render_subfolder(root, '投标文档')
    instance.tender_folder = tender_dir
    instance.bid_folder = bid_dir
    db.add(instance)
    db.commit()
    db.refresh(instance)

    rebuilt = tender_dir if folder_type == 'tender' else bid_dir
    return rebuilt, project_name, 'recovered'