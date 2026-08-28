"""文件存储配置管理 + 上传端点
- 读取/更新配置
- 测试连通性
- 预览项目路径
- 拖拽上传到指定子目录（tender/bid）
- 诊断所有项目的存储路径（不修改 DB）
- 重建指定项目的 WebDAV 目录（仅管理员）
"""
import logging
import os
import re
import unicodedata
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import FileStorageConfig, StorageMode, AuditAction
from app.schemas import (
    FileStorageConfigResponse, FileStorageConfigUpdate,
    PathPreviewRequest, PathPreviewResponse, MessageResponse,
)
from app.auth import get_current_user, require_admin
from app.services.file_storage import (
    render_project_root, render_subfolder, test_connection, sanitize_path_segment,
)
from app.services.audit import write_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/file-storage', tags=['文件管理'])

# 单文件最大 500MB（前端也应该做同样限制防止 DoS）
# 可在 config.yaml -> upload.max_file_size_mb 覆盖
_MAX_FILE_SIZE_DEFAULT = 500 * 1024 * 1024  # 500MB
_CHUNK_SIZE = 1024 * 1024  # 1MB 流式分块


def _get_max_file_size(db: Session) -> int:
    """从 config.yaml 读取 max_file_size_mb，未配置则用默认 500MB"""
    try:
        from app.database import load_config
        cfg = load_config()
        mb = int(cfg.get('upload', {}).get('max_file_size_mb', 500))
        return mb * 1024 * 1024
    except Exception:
        return _MAX_FILE_SIZE_DEFAULT


def _read_upload_streaming(upload_file: UploadFile, max_size: int, on_progress=None):
    """流式读取 UploadFile 到字节数组，超过 max_size 抛错
    - 每次读 _CHUNK_SIZE 字节（1MB）
    - 已读超过 max_size 立即中止抛 HTTPException(413)
    - on_progress(bytes_read) 回调用于扩展（前端有 xhr.upload.onprogress 已经够用, 这里保留）
    """
    import asyncio
    received = bytearray()
    try:
        while True:
            chunk = upload_file.file.read(_CHUNK_SIZE)
            if not chunk:
                break
            received.extend(chunk)
            if on_progress:
                try:
                    on_progress(len(received))
                except Exception:
                    pass
            if len(received) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f'文件 {upload_file.filename!r} 超过单文件大小限制 '
                           f'({max_size // 1024 // 1024}MB)，请压缩后分批上传',
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'读取上传流失败: {e}')
    return bytes(received)

def _ensure_config(db: Session) -> FileStorageConfig:
    cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    if not cfg:
        cfg = FileStorageConfig(id=1, mode=StorageMode.local)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

def _resolve_config_for_project(db: Session, project_id) -> FileStorageConfig:
    """根据 project_id 反查正确的 cfg（StorageZone 优先；fallback 老单例）

    用途：list/upload/delete 三个端点必须用项目实际关联的 zone 配置，
    否则项目用 admin001 账号建了目录，但操作却用 trae 单例 → 401 Unauthorized。
    """
    from app.models import Project, StorageZone
    try:
        pid = int(project_id) if project_id else None
    except Exception:
        pid = None

    if pid:
        try:
            proj = db.query(Project).filter(Project.id == pid).first()
            if proj and proj.storage_zone_id:
                zone = db.query(StorageZone).filter(StorageZone.id == proj.storage_zone_id).first()
                if zone:
                    return FileStorageConfig(
                        id=9999 + (zone.id or 0),
                        mode=zone.mode or StorageMode.webdav,
                        webdav_url=zone.webdav_url,
                        webdav_port=zone.webdav_port,
                        webdav_username=zone.webdav_username,
                        webdav_password=zone.webdav_password,
                        webdav_base_path=zone.webdav_base_path,
                        webdav_use_ssl=zone.webdav_use_ssl if zone.webdav_use_ssl is not None else True,
                        local_path=zone.local_path,
                        template='{responsible_sales}+{project_name}+{date}',
                    )
        except Exception as e:
            logger.exception(f"_resolve_config_for_project 反查失败: {e}")
    return _ensure_config(db)

def _resolve_target_dir_self_healing(
    db: Session,
    project_id,
    folder_type: str,
    sub_label: str,
) -> tuple[str, str, str]:
    """自修复：根据 project_id 解析出真实的存盘目录。

    返回: (target_dir, project_name, db_resolved_or_recovered)
        - target_dir: 用于 list / upload 的真实路径
        - project_name: 调试用
        - db_resolved_or_recovered: 'db' = 数据库已有；
                                     'recovered' = 字段为空，按 creator+name 重建并回写；
                                     'missing' = 项目不存在 / 无法解析
    """
    if not project_id:
        return '', '', 'missing'
    try:
        from app.models import Project, User
        proj = db.query(Project).filter(Project.id == int(project_id)).first()
        if not proj:
            return '', '', 'missing'
        project_name = proj.project_name or ''
        # 1) 数据库已有 → 直接用
        target_dir = (proj.tender_folder if folder_type == 'tender' else proj.bid_folder) or ''
        if target_dir:
            return target_dir, project_name, 'db'
        # 2) 数据库为空 → 自修复：用 creator + project_name 拼路径，回写
        if project_name:
            owner_username = ''
            owner_real_name = ''
            if proj.created_by:
                owner = db.query(User).filter(User.id == proj.created_by).first()
                if owner:
                    owner_username = owner.username or ''
                    owner_real_name = owner.real_name or ''
            if not owner_username:
                return '', project_name, 'missing'
            cfg = _resolve_config_for_project(db, project_id)
            root = render_project_root(cfg, owner_username, owner_real_name, project_name)
            rebuilt = render_subfolder(root, sub_label)
            if rebuilt:
                try:
                    if folder_type == 'tender':
                        proj.tender_folder = rebuilt
                    else:
                        proj.bid_folder = rebuilt
                    db.add(proj)
                    db.commit()
                    db.refresh(proj)
                    logger.warning(
                        f"[self-heal] project_id={project_id} folder_type={folder_type} "
                        f"DB folder 为空 → 已重建并回写: {rebuilt}"
                    )
                except Exception as e:
                    logger.exception(f"[self-heal] 回写 project.{folder_type}_folder 失败: {e}")
                return rebuilt, project_name, 'recovered'
        return '', project_name, 'missing'
    except Exception as e:
        logger.exception(f"_resolve_target_dir_self_healing 出错: {e}")
        return '', '', 'missing'

@router.get('/config', response_model=FileStorageConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """读取文件存储配置（所有登录用户可读）"""
    cfg = _ensure_config(db)
    resp = FileStorageConfigResponse.model_validate(cfg)
    if cfg.webdav_password:
        resp.webdav_password = '******'
    return resp

@router.put('/config', response_model=FileStorageConfigResponse)
def update_config(
    data: FileStorageConfigUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """更新文件存储配置（仅管理员）"""
    cfg = _ensure_config(db)
    cfg.mode = data.mode
    if data.local_path is not None:
        cfg.local_path = data.local_path or None
    if data.webdav_url is not None:
        cfg.webdav_url = data.webdav_url or None
    if data.webdav_port is not None:
        cfg.webdav_port = data.webdav_port if data.webdav_port > 0 else None
    if data.webdav_use_ssl is not None:
        cfg.webdav_use_ssl = data.webdav_use_ssl
    if data.webdav_username is not None:
        cfg.webdav_username = data.webdav_username or None
    if data.webdav_password and data.webdav_password != '******':
        cfg.webdav_password = data.webdav_password
    if data.webdav_base_path is not None:
        cfg.webdav_base_path = data.webdav_base_path or None
    if data.template is not None:
        cfg.template = data.template or '{real_name}+{project_name}+{date}'
    db.commit()
    db.refresh(cfg)

    resp = FileStorageConfigResponse.model_validate(cfg)
    if cfg.webdav_password:
        resp.webdav_password = '******'
    return resp

@router.post('/test-connection', response_model=MessageResponse)
def test_storage_connection(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """测试当前配置连通性（仅管理员）"""
    cfg = _ensure_config(db)
    ok, msg = test_connection(cfg)
    return MessageResponse(message=('✓ ' if ok else '✗ ') + msg)

@router.post('/preview-path', response_model=PathPreviewResponse)
def preview_path(
    data: PathPreviewRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """预览项目路径（不实际建）"""
    from app.models import Project, User, StorageZone

    username = data.creator_username or _user.username
    real_name = data.creator_real_name or _user.real_name
    if not data.creator_username or not data.creator_real_name:
        try:
            proj = db.query(Project).filter(Project.project_name == data.project_name).first()
            if proj and proj.created_by:
                owner = db.query(User).filter(User.id == proj.created_by).first()
                if owner:
                    username = owner.username
                    real_name = owner.real_name
        except Exception:
            pass

    cfg_obj = None
    # 任何 source 都可能要走 zone 解析：
    #   - source='self' 且 storage_zone_id：直接用 zone
    #   - source='self' 但没传 zone：从已存在的 Project 反查
    #   - source='channel'：从「渠道项目登记表」FormTemplate 反查 zone（如果模板绑定了）
    #   - 兜底：老单例 FileStorageConfig.id == 1
    need_resolve_zone = (
        data.source == 'self'
        or data.storage_zone_id
        or data.source == 'channel'  # ★ 新增：渠道项目也要走 zone 解析
    )
    if need_resolve_zone:
        zid = data.storage_zone_id
        if not zid and data.source == 'self':
            # 自营项目：从已存在 Project 反查
            try:
                proj = db.query(Project).filter(Project.project_name == data.project_name).first()
                zid = proj.storage_zone_id if proj else None
            except Exception:
                zid = None
        if not zid and data.source == 'channel':
            # ★ 渠道项目：从「渠道项目登记表」FormTemplate 反查 zone
            try:
                from app.models import FormTemplate
                tpl = db.query(FormTemplate).filter(
                    FormTemplate.name.like('%渠道项目%'),
                    FormTemplate.is_active == True,
                ).first()
                if tpl and tpl.storage_zone_id:
                    zid = tpl.storage_zone_id
                    logger.info(f"[preview-path] 渠道项目用模板「{tpl.name}」的 storage_zone_id={zid}")
            except Exception as e:
                logger.warning(f"[preview-path] 反查渠道项目模板 zone 失败: {e}")
        zone = db.query(StorageZone).filter(StorageZone.id == zid).first() if zid else None
        if zone:
            cfg_obj = FileStorageConfig(
                id=9999 + zone.id,
                mode=zone.mode,
                webdav_url=zone.webdav_url,
                webdav_port=zone.webdav_port,
                webdav_username=zone.webdav_username,
                webdav_password=zone.webdav_password,
                webdav_base_path=zone.webdav_base_path,
                webdav_use_ssl=zone.webdav_use_ssl,
                local_path=zone.local_path,
                template='{responsible_sales}+{project_name}+{date}',
            )

    if cfg_obj is None:
        cfg_obj = _ensure_config(db)

    # ★ 关键修复：如果项目已存在 + DB 里有 tender_folder/bid_folder，优先返回 DB 里的路径
    # 原因：{responsible_sales}+{project_name}+{date} 模板里的 {date} 用 datetime.now()，
    #       每次重新渲染日期都会变；建项目时的日期才是"真理"，DB 已记录。
    #       不然用户今天建项目(2026-08-27)，明天上传时界面显示"2026-08-28"造成路径不一致
    db_tender = ''
    db_bid = ''
    db_proj_for_preview = None
    try:
        db_proj_for_preview = db.query(Project).filter(Project.project_name == data.project_name).first()
        if db_proj_for_preview:
            db_tender = (db_proj_for_preview.tender_folder or '').strip()
            db_bid = (db_proj_for_preview.bid_folder or '').strip()
    except Exception:
        pass

    root = render_project_root(cfg_obj, username, real_name, data.project_name, data.responsible_sales)
    tender = render_subfolder(root, '招标资料')
    bid = render_subfolder(root, '投标文档')

    # 已存在项目：用 DB 路径（保持建项目时的日期不动）
    if db_proj_for_preview and (db_tender or db_bid):
        return PathPreviewResponse(
            base_folder=root,  # 仅供参考,前端不会显示
            tender_folder=db_tender or tender,
            bid_folder=db_bid or bid,
        )

    # 新项目（DB 没有记录）：返回实时渲染的路径（前端用来给用户预览）
    return PathPreviewResponse(
        base_folder=root,
        tender_folder=tender,
        bid_folder=bid,
    )

# === 列表 / 上传 / 删除 ===
@router.post('/list-files')
async def list_files(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出指定子目录下的已上传文件"""
    try:
        body = await request.json()
    except Exception as e:
        logger.exception(f'list-files: 解析请求体失败: {e}')
        raise HTTPException(400, detail='请求体必须是 JSON')

    folder_type = body.get('folder_type')
    if not folder_type:
        raise HTTPException(400, detail='folder_type 必填')
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail=f'folder_type 必须是 tender 或 bid，收到: {folder_type}')

    sub_label = '招标资料' if folder_type == 'tender' else '投标文档'
    project_id = body.get('project_id')
    project_name_hint = body.get('project_name') or ''
    db_source = ''

    target_dir = ''
    if project_id:
        target_dir, project_name_hint, db_source = _resolve_target_dir_self_healing(
            db, project_id, folder_type, sub_label
        )

    if not target_dir:
        target_dir = (body.get('target_dir') or '').strip()
        if target_dir:
            db_source = 'client'

    if not target_dir and project_name_hint:
        creator_username = body.get('creator_username') or current_user.username
        creator_real_name = body.get('creator_real_name') or current_user.real_name
        cfg = _resolve_config_for_project(db, project_id)
        root = render_project_root(cfg, creator_username, creator_real_name, project_name_hint)
        target_dir = render_subfolder(root, sub_label)
        db_source = 'fallback'

    logger.info(
        f"[list-files] project_id={project_id} folder_type={folder_type} "
        f"db_source={db_source} project_name={project_name_hint!r} target_dir={target_dir!r}"
    )

    if not target_dir:
        return {
            'folder': '',
            'folder_type': folder_type,
            'files': [],
            'db_source': db_source,
        }

    cfg = _resolve_config_for_project(db, project_id)
    files = []
    if cfg.mode == StorageMode.local:
        if not os.path.isdir(target_dir):
            return {
                'folder': target_dir,
                'folder_type': folder_type,
                'files': [],
                'db_source': db_source,
            }
        try:
            for entry in os.listdir(target_dir):
                full_path = os.path.join(target_dir, entry)
                if os.path.isfile(full_path):
                    try:
                        stat = os.stat(full_path)
                        files.append({
                            'name': entry,
                            'path': full_path,
                            'size': stat.st_size,
                            'mtime': int(stat.st_mtime),
                        })
                    except OSError as e:
                        logger.exception(f"[list-files] stat 文件失败: {full_path}: {e}")
        except OSError as e:
            logger.exception(f"[list-files] 读取目录失败: {target_dir}: {e}")
            raise HTTPException(500, detail=f'读取目录失败: {e}')
    else:
        try:
            from app.services.webdav_client import list_files_webdav
            ok, file_list = list_files_webdav(cfg, target_dir, project_name_hint=project_name_hint)
            if ok:
                files = file_list
            else:
                logger.warning(f"[list-files] WebDAV list 失败: target_dir={target_dir}")
        except Exception as e:
            logger.exception(f"[list-files] WebDAV 列出文件异常: {e}")
            raise HTTPException(500, detail=f'WebDAV 列出文件失败: {e}')

    logger.info(
        f"[list-files] ✓ resolved_dir={target_dir!r} files_count={len(files)} db_source={db_source}"
    )
    return {
        'folder': target_dir,
        'folder_type': folder_type,
        'files': files,
        'db_source': db_source,
    }

class DeleteFileRequest(BaseModel):
    project_id: Optional[int] = None
    folder_type: Optional[str] = None
    file_name: Optional[str] = None

@router.post('/delete-file', response_model=MessageResponse)
async def delete_storage_file(
    data: DeleteFileRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定文件（仅系统管理员）"""
    if not current_user or current_user.role.value != 'admin':
        raise HTTPException(status_code=403, detail='仅系统管理员可删除文件')

    if not data.project_id:
        raise HTTPException(400, detail='project_id 必填')
    if data.folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail='folder_type 必须是 tender 或 bid')
    if not data.file_name or not data.file_name.strip():
        raise HTTPException(400, detail='file_name 必填')

    sub_label = '招标资料' if data.folder_type == 'tender' else '投标文档'
    file_name = data.file_name.strip()
    if '/' in file_name or '\\' in file_name or '..' in file_name:
        raise HTTPException(400, detail=f'非法的 file_name: {file_name!r}')

    target_dir, project_name, db_source = _resolve_target_dir_self_healing(
        db, data.project_id, data.folder_type, sub_label
    )
    if not target_dir:
        raise HTTPException(404, detail=f'无法解析项目 {data.project_id} 的目录')

    full_path = os.path.join(target_dir, file_name)
    target_abs = os.path.abspath(target_dir)
    full_abs = os.path.abspath(full_path)
    if not (full_abs == target_abs or full_abs.startswith(target_abs + os.sep)):
        raise HTTPException(400, detail='路径越权')

    cfg = _resolve_config_for_project(db, data.project_id)
    deleted = False
    try:
        if cfg.mode == StorageMode.local:
            if os.path.isfile(full_abs):
                os.remove(full_abs)
                deleted = True
            else:
                raise HTTPException(404, detail=f'文件不存在: {full_abs}')
        else:
            try:
                from app.services.webdav_client import delete_file_webdav
                if not target_dir.startswith('http'):
                    raise HTTPException(500, detail='WebDAV 模式下 target_dir 必须是 http(s) URL')
                target_url = target_dir.rstrip('/') + '/' + file_name
                ok = delete_file_webdav(cfg, target_url)
                if ok:
                    deleted = True
                else:
                    raise HTTPException(500, detail='WebDAV 删除失败')
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f'delete-file: WebDAV 异常: {e}')
                raise HTTPException(500, detail=f'WebDAV 删除异常: {e}')
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'delete-file 异常: {e}')
        raise HTTPException(500, detail=f'删除失败: {e}')

    if not deleted:
        raise HTTPException(500, detail='删除失败（未知原因）')

    try:
        from app.models import Project
        proj = db.query(Project).filter(Project.id == data.project_id).first()
        proj_name = proj.project_name if proj else f'id={data.project_id}'
        write_audit(
            current_user, AuditAction.file_delete,
            target_type='file', target_id=None,
            target_name=f"{proj_name} / {sub_label} / {file_name}",
            details={'project_id': data.project_id, 'folder_type': data.folder_type,
                     'file_name': file_name, 'full_path': full_abs,
                     'db_source': db_source},
        )
    except Exception as e:
        logger.exception(f'delete-file: 写审计失败: {e}')

    logger.info(f"[delete-file] admin={current_user.username} project_id={data.project_id} "
                f"folder_type={data.folder_type} file_name={file_name!r} db_source={db_source}")
    return MessageResponse(message=f'✓ 已删除 {file_name}')

@router.post('/upload')
async def upload_files(
    folder_type: str = Form(...),
    project_name: str = Form(..., min_length=1),
    files: List[UploadFile] = File(...),
    creator_username: str = Form(default=''),
    creator_real_name: str = Form(default=''),
    target_dir: str = Form(default=''),
    overwrite: str = Form(default='false'),
    project_id: str = Form(default=''),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """拖拽上传文件到当前项目目录的指定子目录"""
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail=f'folder_type 必须是 tender 或 bid，收到: {folder_type}')
    if not files or len(files) == 0:
        raise HTTPException(400, detail='未选择文件')

    sub_label = '招标资料' if folder_type == 'tender' else '投标文档'
    cfg = _resolve_config_for_project(db, project_id)

    db_target_dir = ''
    if project_id:
        try:
            from app.models import Project
            proj = db.query(Project).filter(Project.id == int(project_id)).first()
            if proj:
                db_target_dir = (proj.tender_folder if folder_type == 'tender' else proj.bid_folder) or ''
        except Exception:
            pass

    user_for_path = creator_username or current_user.username
    real_name_for_path = creator_real_name or current_user.real_name
    rendered_root = render_project_root(cfg, user_for_path, real_name_for_path, project_name)
    rendered_dir = render_subfolder(rendered_root, sub_label)

    target_dir = db_target_dir or (target_dir or '').strip() or rendered_dir
    overwrite_flag = str(overwrite).lower() in ('1', 'true', 'yes')

    uploaded = []
    failed = []
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    max_size = _get_max_file_size(db)

    for f in files:
        original = f.filename or f'unknown_{timestamp}'
        safe_name = sanitize_path_segment(original)
        if not safe_name:
            safe_name = f'file_{timestamp}'
        final_name = safe_name
        counter = 1

        try:
            # 流式分块读取（避免大文件占用过多内存 + 实时检查大小）
            content = _read_upload_streaming(f, max_size)
            if cfg.mode == StorageMode.local:
                os.makedirs(target_dir, exist_ok=True)
                full_path = os.path.join(target_dir, final_name)
                if os.path.exists(full_path):
                    if overwrite_flag:
                        try:
                            os.remove(full_path)
                        except OSError:
                            pass
                    else:
                        while os.path.exists(full_path):
                            base, ext = os.path.splitext(safe_name)
                            final_name = f'{base}_{counter}{ext}'
                            full_path = os.path.join(target_dir, final_name)
                            counter += 1
                try:
                    with open(full_path, 'wb') as out:
                        out.write(content)
                    uploaded.append({
                        'name': final_name,
                        'path': full_path,
                        'size': len(content),
                        'uploader': current_user.real_name or current_user.username,
                        'uploader_username': current_user.username,
                        'upload_time': int(datetime.now().timestamp()),
                        'overwritten': overwrite_flag and final_name == safe_name,
                    })
                except Exception as _e:
                    import traceback as _tb
                    failed.append({'name': final_name, 'error': f'{type(_e).__name__}: {_e} | dir w={os.access(target_dir, os.W_OK)} | exists={os.path.exists(full_path)} | cwd={os.getcwd()} | tb={_tb.format_exc()[:500]}'})
                    raise
            else:
                try:
                    from app.services.webdav_client import upload_file, delete_file_webdav, list_files_webdav
                    webdav_target = target_dir if target_dir.startswith('http') else render_subfolder(rendered_root, sub_label)
                    target_url = webdav_target.rstrip('/') + '/' + final_name
                    if not target_url.startswith('http'):
                        target_url = 'http://invalid' + target_url
                    overwritten = False
                    if overwrite_flag:
                        ok_list, existing = list_files_webdav(cfg, webdav_target, project_name_hint=project_name)
                        if ok_list and any(x.get('name') == final_name for x in existing):
                            delete_file_webdav(cfg, target_url)
                            overwritten = True
                    ok, msg = upload_file(cfg, target_url, content)
                    if ok:
                        uploaded.append({
                            'name': final_name,
                            'path': target_url,
                            'size': len(content),
                            'uploader': current_user.real_name or current_user.username,
                            'uploader_username': current_user.username,
                            'upload_time': int(datetime.now().timestamp()),
                            'overwritten': overwritten,
                        })
                    else:
                        failed.append({'name': final_name, 'error': msg})
                except Exception as e:
                    failed.append({'name': final_name, 'error': f'WebDAV 错误: {e}'})
        except Exception as e:
            failed.append({'name': original, 'error': str(e)})
        finally:
            await f.close()

    if uploaded:
        try:
            write_audit(
                current_user, AuditAction.file_upload,
                target_type='file', target_id=None,
                target_name=f"{project_name} / {sub_label}",
                details={'folder_type': folder_type, 'files': [f['name'] for f in uploaded],
                         'total_size': sum(f['size'] for f in uploaded),
                         'failed_count': len(failed)},
                request=request,
            )
        except Exception as e:
            logger.exception(f"[upload] 写审计失败: {e}")

    if project_id and uploaded:
        try:
            from app.models import Project
            proj = db.query(Project).filter(Project.id == int(project_id)).first()
            if proj:
                if folder_type == 'tender':
                    if proj.tender_folder != target_dir:
                        proj.tender_folder = target_dir
                        db.add(proj)
                else:
                    if proj.bid_folder != target_dir:
                        proj.bid_folder = target_dir
                        db.add(proj)
                db.commit()
                db.refresh(proj)
                logger.info(
                    f"[upload] 已回写 Project(id={project_id}).{folder_type}_folder = {target_dir!r}"
                )
        except Exception as e:
            logger.exception(f"[upload] 回写 Project.{folder_type}_folder 失败: {e}")

    logger.info(
        f"[upload] project_id={project_id} folder_type={folder_type} "
        f"target_dir={target_dir!r} uploaded={len(uploaded)} failed={len(failed)}"
    )
    return {
        'success': len(failed) == 0,
        'folder': target_dir,
        'folder_type': folder_type,
        'uploaded': uploaded,
        'failed': failed,
        'total': len(files),
    }

# === D1：诊断所有项目的存储路径（不修改 DB）===
@router.post('/diagnose-all')
def diagnose_all(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """扫描所有项目的 tender_folder / bid_folder，PROPFIND 校验但不修改 DB。

    返回每个项目的状态：
      - ok      : 目录可访问
      - wrong   : 目录不可访问（401/404/网络错误等）
      - empty   : DB 字段为空
      - unknown : 项目无关联 zone（无法判断）
    """
    from app.models import Project, StorageZone

    items = []
    summary = {"total": 0, "ok": 0, "wrong": 0, "empty": 0, "unknown": 0}

    projs = db.query(Project).all()
    for proj in projs:
        item = {
            "project_id": proj.id,
            "project_name": proj.project_name,
            "tender_folder": proj.tender_folder or "",
            "bid_folder": proj.bid_folder or "",
            "storage_zone_id": proj.storage_zone_id,
            "tender_status": "unknown",
            "tender_msg": "",
            "bid_status": "unknown",
            "bid_msg": "",
        }

        if proj.storage_zone_id is None:
            item["tender_status"] = "unknown"
            item["bid_status"] = "unknown"
            item["tender_msg"] = "项目未关联 storage_zone"
            item["bid_msg"] = "项目未关联 storage_zone"
            summary["unknown"] += 1
            items.append(item)
            continue

        cfg = _resolve_config_for_project(db, proj.id)

        for folder_type, key in (("tender", "tender_folder"), ("bid", "bid_folder")):
            url = getattr(proj, key) or ""
            status_key = f"{folder_type}_status"
            msg_key = f"{folder_type}_msg"
            if not url:
                item[status_key] = "empty"
                item[msg_key] = "DB 字段为空"
                continue
            if cfg.mode == StorageMode.local:
                if os.path.isdir(url):
                    item[status_key] = "ok"
                    item[msg_key] = "本地目录可访问"
                    summary["ok"] += 1
                else:
                    item[status_key] = "wrong"
                    item[msg_key] = f"本地目录不存在: {url}"
                    summary["wrong"] += 1
            else:
                # WebDAV：PROPFIND 探测（用 probe_dir_exists 真实探测）
                try:
                    from app.services.webdav_client import probe_dir_exists
                    if probe_dir_exists(cfg, url, timeout=4):
                        item[status_key] = "ok"
                        item[msg_key] = "WebDAV 目录可访问"
                        summary["ok"] += 1
                    else:
                        item[status_key] = "wrong"
                        item[msg_key] = f"PROPFIND 探测失败: {url}"
                        summary["wrong"] += 1
                except Exception as e:
                    item[status_key] = "wrong"
                    item[msg_key] = f"探测异常: {e}"
                    summary["wrong"] += 1

        items.append(item)

    summary["total"] = len(projs)
    return {"items": items, "summary": summary}

# === D2：重建指定项目的 WebDAV 目录（仅管理员）===
class RebuildFoldersRequest(BaseModel):
    project_id: int

@router.post('/rebuild-project-folders', response_model=MessageResponse)
async def rebuild_project_folders(
    data: RebuildFoldersRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """按项目当前 DB 字段（不重算）调 ensure_webdav_folders 重建子目录。

    仅 admin。不会修改 tender_folder / bid_folder 字段。
    """
    if not current_user or current_user.role.value != 'admin':
        raise HTTPException(status_code=403, detail='仅系统管理员可重建目录')

    from app.models import Project
    proj = db.query(Project).filter(Project.id == data.project_id).first()
    if not proj:
        raise HTTPException(404, detail=f'项目不存在: {data.project_id}')

    cfg = _resolve_config_for_project(db, data.project_id)
    if cfg.mode == StorageMode.local:
        # 本地模式：直接 makedirs
        try:
            for url in (proj.tender_folder, proj.bid_folder):
                if url:
                    os.makedirs(url, exist_ok=True)
            return MessageResponse(message='✓ 本地目录已就绪')
        except Exception as e:
            logger.exception(f'rebuild-project-folders 本地失败: {e}')
            raise HTTPException(500, detail=f'本地重建失败: {e}')

    # WebDAV 模式：对每个非空 folder 做 MKCOL（含"招标资料"/"投标文档"两个子目录）
    from app.services.webdav_client import probe_dir_exists, _request
    msgs = []
    try:
        # proj.tender_folder 形如 https://nas/dav/项目根/招标资料 → 实际是叶子目录
        # 这里直接对叶子目录做 MKCOL（已存在会得到 405 Method Not Allowed，按成功跳过）
        for root_url, sub in ((proj.tender_folder or '', '招标资料'), (proj.bid_folder or '', '投标文档')):
            if not root_url:
                msgs.append(f'{sub}: DB 为空，跳过')
                continue
            # 先探测是否已存在
            if probe_dir_exists(cfg, root_url, timeout=4):
                msgs.append(f'{sub}({root_url}): 已存在')
                continue
            # 不存在则 MKCOL
            try:
                resp = _request('MKCOL', root_url, cfg, timeout=15)
                code = resp.status_code
                if code in (201, 405):  # 201 Created / 405 已存在
                    msgs.append(f'{sub}({root_url}): 新建成功' if code == 201 else f'{sub}({root_url}): 已存在(405)')
                else:
                    raise RuntimeError(f'{sub} MKCOL 返回 {code}')
            except Exception as e:
                raise RuntimeError(f'{sub} 创建失败: {e}')
        return MessageResponse(message='✓ 重建完成: ' + '; '.join(msgs))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'rebuild-project-folders 失败: {e}')
        raise HTTPException(500, detail=f'重建失败: {e}')