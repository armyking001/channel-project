"""存储区域管理 — 用户自定义的本地/WebDAV 文件存储位置
每个项目/表单可选择使用哪个区域
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.auth import get_current_user
from app.models import User, UserRole, StorageZone, StorageMode
from app.schemas import (
    StorageZoneCreate, StorageZoneUpdate, StorageZoneResponse,
    StorageZoneListResponse,
)
from app.services.audit import write_audit, AuditAction
from app.services.file_storage import _test_webdav_connection, _test_local_connection

router = APIRouter(prefix="/api/storage-zones", tags=["storage-zones"])


def _require_admin(current_user: User):
    if current_user.role != UserRole.admin:
        raise HTTPException(403, detail="仅系统管理员可管理存储区域")


def _to_response(z: StorageZone) -> dict:
    """转换为响应结构（密码掩码）"""
    return {
        'id': z.id,
        'name': z.name,
        'mode': z.mode.value if hasattr(z.mode, 'value') else z.mode,
        'local_path': z.local_path,
        'webdav_url': z.webdav_url,
        'webdav_port': z.webdav_port,
        'webdav_use_ssl': bool(z.webdav_use_ssl) if z.webdav_use_ssl is not None else True,
        'webdav_username': z.webdav_username,
        'webdav_password_masked': '******' if z.webdav_password else None,
        'webdav_base_path': z.webdav_base_path,
        'sub_path': z.sub_path,
        'description': z.description,
        'is_active': bool(z.is_active) if z.is_active is not None else True,
        'sort_order': z.sort_order or 0,
        'created_at': z.created_at,
        'updated_at': z.updated_at,
    }


@router.get("", response_model=StorageZoneListResponse)
def list_storage_zones(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出所有存储区域"""
    zones = db.query(StorageZone).order_by(StorageZone.sort_order, StorageZone.id).all()
    items = [_to_response(z) for z in zones]
    return {"items": items, "total": len(items)}


@router.post("", response_model=StorageZoneResponse)
def create_storage_zone(
    request: Request,
    data: StorageZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建存储区域"""
    _require_admin(current_user)

    if data.mode not in ('local', 'webdav'):
        raise HTTPException(400, detail="mode 必须是 'local' 或 'webdav'")

    if data.mode == 'local' and not data.local_path:
        raise HTTPException(400, detail="本地模式必须指定 local_path")
    if data.mode == 'webdav' and not data.webdav_url:
        raise HTTPException(400, detail="WebDAV 模式必须指定 webdav_url")

    # 名称唯一
    existing = db.query(StorageZone).filter(StorageZone.name == data.name).first()
    if existing:
        raise HTTPException(400, detail=f"已存在同名区域「{data.name}」")

    zone = StorageZone(
        name=data.name,
        mode=StorageMode(data.mode),
        local_path=data.local_path,
        webdav_url=data.webdav_url,
        webdav_port=data.webdav_port,
        webdav_use_ssl=data.webdav_use_ssl,
        webdav_username=data.webdav_username,
        webdav_password=data.webdav_password,
        webdav_base_path=data.webdav_base_path,
        sub_path=data.sub_path,
        description=data.description,
        sort_order=data.sort_order,
        is_active=True,
    )
    db.add(zone)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, detail="创建失败：名称冲突")
    db.refresh(zone)

    write_audit(current_user, AuditAction.user_update if False else AuditAction.user_update,
                target_type='storage_zone', target_id=zone.id, target_name=zone.name,
                request=request,
                details={'action': 'create', 'msg': f"创建存储区域: {zone.name}"})

    return _to_response(zone)


@router.get("/{zone_id}", response_model=StorageZoneResponse)
def get_storage_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zone = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, detail="存储区域不存在")
    return _to_response(zone)


@router.get("/{zone_id}/reveal-password")
def reveal_password(
    request: Request,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """显示明文密码（仅管理员；审计记录）"""
    _require_admin(current_user)
    zone = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, detail="存储区域不存在")

    write_audit(current_user, AuditAction.user_update,
                target_type='storage_zone', target_id=zone.id, target_name=zone.name,
                request=request,
                details={'action': 'reveal_password', 'msg': f"查看密码: {zone.name}"})

    return {"password": zone.webdav_password or ''}


@router.put("/{zone_id}", response_model=StorageZoneResponse)
def update_storage_zone(
    request: Request,
    zone_id: int,
    data: StorageZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新存储区域"""
    _require_admin(current_user)
    zone = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, detail="存储区域不存在")

    updates = data.model_dump(exclude_unset=True)
    if 'mode' in updates:
        if updates['mode'] not in ('local', 'webdav'):
            raise HTTPException(400, detail="mode 必须是 'local' 或 'webdav'")
        zone.mode = StorageMode(updates['mode'])

    # 名称查重
    if 'name' in updates and updates['name'] != zone.name:
        existing = db.query(StorageZone).filter(StorageZone.name == updates['name']).first()
        if existing:
            raise HTTPException(400, detail=f"已存在同名区域「{updates['name']}」")

    # 如果密码掩码「******」则保留原密码
    if updates.get('webdav_password') == '******':
        updates.pop('webdav_password', None)

    for k, v in updates.items():
        if k == 'mode':
            continue  # 已处理
        setattr(zone, k, v)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, detail="更新失败")
    db.refresh(zone)

    write_audit(current_user, AuditAction.user_update,
                target_type='storage_zone', target_id=zone.id, target_name=zone.name,
                request=request,
                details={'action': 'update', 'msg': f"更新存储区域: {zone.name}"})

    return _to_response(zone)


@router.delete("/{zone_id}")
def delete_storage_zone(
    request: Request,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除存储区域（如果有项目/表单正在使用，则拒绝删除）"""
    _require_admin(current_user)
    zone = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, detail="存储区域不存在")

    # 检查是否被使用
    from app.models import Project as ProjectModel, FormTemplate as FormTemplateModel
    used_by_projects = db.query(ProjectModel).filter(ProjectModel.storage_zone_id == zone_id).count()
    used_by_templates = db.query(FormTemplateModel).filter(FormTemplateModel.storage_zone_id == zone_id).count()
    if used_by_projects > 0 or used_by_templates > 0:
        raise HTTPException(400, detail=f"该区域正在被 {used_by_projects} 个项目 / {used_by_templates} 个表单使用，无法删除")

    zone_name = zone.name
    db.delete(zone)
    db.commit()

    write_audit(current_user, AuditAction.user_update,
                target_type='storage_zone', target_id=zone_id, target_name=zone_name,
                request=request,
                details={'action': 'delete', 'msg': f"删除存储区域: {zone_name}"})

    return {"deleted": True, "id": zone_id}


@router.post("/{zone_id}/test-connection")
def test_zone_connection(
    request: Request,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试存储区域连接"""
    zone = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, detail="存储区域不存在")

    if zone.mode == StorageMode.local:
        ok, msg = _test_local_connection(zone.local_path or '')
    else:
        ok, msg = _test_webdav_connection(
            base_url=zone.webdav_url or '',
            port=zone.webdav_port,
            use_ssl=bool(zone.webdav_use_ssl),
            username=zone.webdav_username or '',
            password=zone.webdav_password or '',
            base_path=zone.webdav_base_path or '',
        )

    return {"ok": ok, "message": msg}