"""文件存储配置管理 + 上传端点
- 读取/更新配置
- 测试连通性
- 预览项目路径
- 拖拽上传到指定子目录（tender/bid）
"""
import logging
import os
import re
import unicodedata
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional

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

router = APIRouter(prefix='/api/file-storage', tags=['文件管理'])


def _ensure_config(db: Session) -> FileStorageConfig:
    cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    if not cfg:
        cfg = FileStorageConfig(id=1, mode=StorageMode.local)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


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
    """预览项目路径（不实际建）
    若前端传入 creator_username/creator_real_name（编辑模式下使用真实创建者），则用之；否则用当前用户
    """
    cfg = _ensure_config(db)
    username = data.creator_username or _user.username
    real_name = data.creator_real_name or _user.real_name
    root = render_project_root(cfg, username, real_name, data.project_name)
    tender = render_subfolder(root, '招标资料')
    bid = render_subfolder(root, '投标文档')
    return PathPreviewResponse(
        base_folder=root,
        tender_folder=tender,
        bid_folder=bid,
    )


# === 上传端点 ===
@router.post('/list-files')
async def list_files(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出指定子目录下的已上传文件（前端用 JSON POST 调用）"""
    # 仅接受 JSON body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail='请求体必须是 JSON')
    folder_type = body.get('folder_type')
    project_name = body.get('project_name')
    if not folder_type:
        raise HTTPException(400, detail='folder_type 必填')
    if not project_name:
        raise HTTPException(400, detail='project_name 必填')
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail=f'folder_type 必须是 tender 或 bid，收到: {folder_type}')
    sub_label = '招标资料' if folder_type == 'tender' else '投标文档'
    creator_username = body.get('creator_username') or current_user.username
    creator_real_name = body.get('creator_real_name') or current_user.real_name
    cfg = _ensure_config(db)
    root = render_project_root(cfg, creator_username, creator_real_name, project_name)
    target_dir = render_subfolder(root, sub_label)

    files = []
    if cfg.mode == StorageMode.local:
        if os.path.isdir(target_dir):
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
                        except OSError:
                            pass
            except OSError as e:
                raise HTTPException(500, detail=f'读取目录失败: {e}')
    else:
        # WebDAV 模式：通过 PROPFIND 列出文件
        try:
            from app.services.webdav_client import list_files_webdav
            ok, file_list = list_files_webdav(cfg, target_dir)
            if ok:
                files = file_list
        except Exception:
            pass

    return {
        'folder': target_dir,
        'folder_type': folder_type,
        'files': files,
    }


@router.post('/upload')
async def upload_files(
    folder_type: str = Form(..., description="tender=招标资料 / bid=投标文档"),
    project_name: str = Form(..., min_length=1),
    files: List[UploadFile] = File(...),
    creator_username: str = Form(default=''),
    creator_real_name: str = Form(default=''),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """拖拽上传文件到当前项目目录的指定子目录（招标资料/投标文档）
    - 所有登录用户可用
    - 支持传入 creator_username/creator_real_name（其他用户为已有项目补充资料）
    - local 模式：直接写到磁盘
    - WebDAV 模式：PUT 到远程
    """
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail=f'folder_type 必须是 tender 或 bid，收到: {folder_type}')
    if not files or len(files) == 0:
        raise HTTPException(400, detail='未选择文件')

    sub_label = '招标资料' if folder_type == 'tender' else '投标文档'
    cfg = _ensure_config(db)
    user_for_path = creator_username or current_user.username
    real_name_for_path = creator_real_name or current_user.real_name
    root = render_project_root(cfg, user_for_path, real_name_for_path, project_name)
    target_dir = render_subfolder(root, sub_label)

    uploaded = []
    failed = []
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    for f in files:
        # 防止文件名冲突：同名加时间戳
        original = f.filename or f'unknown_{timestamp}'
        safe_name = sanitize_path_segment(original)
        if not safe_name:
            safe_name = f'file_{timestamp}'
        # 同名加序号
        final_name = safe_name
        counter = 1
        if cfg.mode == StorageMode.local:
            full_path = os.path.join(target_dir, final_name)
            while os.path.exists(full_path):
                base, ext = os.path.splitext(safe_name)
                final_name = f'{base}_{counter}{ext}'
                full_path = os.path.join(target_dir, final_name)
                counter += 1
        try:
            content = await f.read()
            if cfg.mode == StorageMode.local:
                os.makedirs(target_dir, exist_ok=True)
                import traceback as _tb
                try:
                    logging.info(f'[upload] target_dir={target_dir} full_path={full_path} w={os.access(target_dir, os.W_OK)} exists={os.path.exists(full_path)}')
                except Exception as _e:
                    logging.info(f'[upload] debug err: {_e}')
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
                    })
                except Exception as _e:
                    import traceback as _tb
                    failed.append({'name': final_name, 'error': f'{type(_e).__name__}: {_e} | dir w={os.access(target_dir, os.W_OK)} | exists={os.path.exists(full_path)} | cwd={os.getcwd()} | tb={_tb.format_exc()[:500]}'})
                    raise
            else:
                # WebDAV 模式
                try:
                    from app.services.webdav_client import upload_file
                    target_url = render_subfolder(root, sub_label).rstrip('/') + '/' + final_name
                    if not target_url.startswith('http'):
                        target_url = 'http://invalid' + target_url  # 防御
                    ok, msg = upload_file(cfg, target_url, content)
                    if ok:
                        uploaded.append({
                            'name': final_name,
                            'path': target_url,
                            'size': len(content),
                            'uploader': current_user.real_name or current_user.username,
                            'uploader_username': current_user.username,
                            'upload_time': int(datetime.now().timestamp()),
                        })
                    else:
                        failed.append({'name': final_name, 'error': msg})
                except Exception as e:
                    failed.append({'name': final_name, 'error': f'WebDAV 错误: {e}'})
        except Exception as e:
            failed.append({'name': original, 'error': str(e)})
        finally:
            await f.close()

    # 审计：只记录成功的上传
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
        except Exception:
            pass

    return {
        'success': len(failed) == 0,
        'folder': target_dir,
        'folder_type': folder_type,
        'uploaded': uploaded,
        'failed': failed,
        'total': len(files),
    }