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


def _ensure_config(db: Session) -> FileStorageConfig:
    cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    if not cfg:
        cfg = FileStorageConfig(id=1, mode=StorageMode.local)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


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
                # 最后兜底：当前 user 拼不出合理路径，留空
                return '', project_name, 'missing'
            cfg = _ensure_config(db)
            root = render_project_root(cfg, owner_username, owner_real_name, project_name)
            rebuilt = render_subfolder(root, sub_label)
            if rebuilt:
                # 回写到数据库
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
    """预览项目路径（不实际建）
    若前端传入 creator_username/creator_real_name（编辑模式下使用真实创建者），则用之；否则用当前用户
    """
    cfg = _ensure_config(db)
    username = data.creator_username or _user.username
    real_name = data.creator_real_name or _user.real_name
    # 如果前端没传 creator_*，则从数据库反查真实创建者
    if not data.creator_username or not data.creator_real_name:
        try:
            from app.models import Project
            proj = db.query(Project).filter(Project.project_name == data.project_name).first()
            if proj and proj.created_by:
                from app.models import User
                owner = db.query(User).filter(User.id == proj.created_by).first()
                if owner:
                    username = owner.username
                    real_name = owner.real_name
        except Exception:
            pass
    root = render_project_root(cfg, username, real_name, data.project_name, data.responsible_sales)
    tender = render_subfolder(root, '招标资料')
    bid = render_subfolder(root, '投标文档')
    # 注意：不再回退到 existing_*_folder 旧值——保证责任销售等字段变动时预览实时跟随
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
    """列出指定子目录下的已上传文件（前端用 JSON POST 调用）

    优先用 project_id 查 Project 表里的 tender_folder/bid_folder（数据库真实存盘路径）。
    若没有 project_id，回退到 project_name + creator_username 模式（兼容旧调用）。
    若 DB 字段为空，会自修复：按 creator + project_name 重建并回写。
    """
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
    db_source = ''  # 'db' | 'recovered' | 'fallback'

    # 1. 优先用 project_id 走自修复解析
    target_dir = ''
    if project_id:
        target_dir, project_name_hint, db_source = _resolve_target_dir_self_healing(
            db, project_id, folder_type, sub_label
        )
        if project_name_hint and not body.get('project_name'):
            project_name_hint = project_name_hint

    # 2. 兼容旧调用：target_dir 字段
    if not target_dir:
        target_dir = (body.get('target_dir') or '').strip()
        if target_dir:
            db_source = 'client'

    # 3. 都没拿到：按 creator + name 拼（不写回 DB）
    if not target_dir and project_name_hint:
        creator_username = body.get('creator_username') or current_user.username
        creator_real_name = body.get('creator_real_name') or current_user.real_name
        cfg = _ensure_config(db)
        root = render_project_root(cfg, creator_username, creator_real_name, project_name_hint)
        target_dir = render_subfolder(root, sub_label)
        db_source = 'fallback'

    # 详细日志（必打的诊断信息）
    logger.info(
        f"[list-files] project_id={project_id} folder_type={folder_type} "
        f"db_source={db_source} project_name={project_name_hint!r} target_dir={target_dir!r}"
    )

    if not target_dir:
        logger.warning(f"[list-files] 无法解析 target_dir → 返回空 files: project_id={project_id}")
        return {
            'folder': '',
            'folder_type': folder_type,
            'files': [],
            'db_source': db_source,
        }

    cfg = _ensure_config(db)
    files = []
    if cfg.mode == StorageMode.local:
        if not os.path.isdir(target_dir):
            logger.warning(f"[list-files] 目录不存在: {target_dir}")
            # 不抛错，返回空列表（前端可以提示）
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
        # WebDAV 模式：通过 PROPFIND 列出文件
        try:
            from app.services.webdav_client import list_files_webdav
            ok, file_list = list_files_webdav(cfg, target_dir, project_name_hint=project_name_hint)
            if ok:
                files = file_list
            else:
                logger.warning(f"[list-files] WebDAV list 失败: target_dir={target_dir}")
        except Exception as e:
            logger.exception(f"[list-files] WebDAV 列出文件异常: {e}")
            # 不吞，向上抛（前端能看到错误）
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
    folder_type: Optional[str] = None  # 'tender' / 'bid'
    file_name: Optional[str] = None    # 文件名（不含路径）


@router.post('/delete-file', response_model=MessageResponse)
async def delete_storage_file(
    data: DeleteFileRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定文件（仅系统管理员可用）

    body: { project_id, folder_type, file_name }
    - 优先用 project_id 查 Project 表里真实的 tender_folder/bid_folder
    - 路径必须严格在项目目录内（防越权）
    """
    # ★ 权限：仅 admin
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
    # 防御：file_name 不允许路径分隔符 / .. 等
    if '/' in file_name or '\\' in file_name or '..' in file_name:
        raise HTTPException(400, detail=f'非法的 file_name: {file_name!r}')

    # 解析真实目录（自修复 + 防御）
    target_dir, project_name, db_source = _resolve_target_dir_self_healing(
        db, data.project_id, data.folder_type, sub_label
    )
    if not target_dir:
        raise HTTPException(404, detail=f'无法解析项目 {data.project_id} 的目录')

    # 拼接完整路径
    full_path = os.path.join(target_dir, file_name)
    # ★ 越权防御：full_path 必须在 target_dir 之内
    target_abs = os.path.abspath(target_dir)
    full_abs = os.path.abspath(full_path)
    if not (full_abs == target_abs or full_abs.startswith(target_abs + os.sep)):
        raise HTTPException(400, detail='路径越权')

    cfg = _ensure_config(db)
    deleted = False
    try:
        if cfg.mode == StorageMode.local:
            if os.path.isfile(full_abs):
                os.remove(full_abs)
                deleted = True
            else:
                raise HTTPException(404, detail=f'文件不存在: {full_abs}')
        else:
            # WebDAV：DELETE
            try:
                from app.services.webdav_client import delete_file_webdav
                # webdav target url 需要是 http(s)://...
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

    # 审计
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
    folder_type: str = Form(..., description="tender=招标资料 / bid=投标文档"),
    project_name: str = Form(..., min_length=1),
    files: List[UploadFile] = File(...),
    creator_username: str = Form(default=''),
    creator_real_name: str = Form(default=''),
    target_dir: str = Form(default=''),
    overwrite: str = Form(default='false', description="true=允许覆盖同名文件"),
    project_id: str = Form(default='', description="项目 ID（用于后端查真实存盘 folder）"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """拖拽上传文件到当前项目目录的指定子目录（招标资料/投标文档）
    - 所有登录用户可用
    - 支持传入 creator_username/creator_real_name（其他用户为已有项目补充资料）
    - 支持 project_id：后端用其查 tender_folder/bid_folder，作为真实存盘路径
    - overwrite=true 时覆盖同名文件；默认按"加序号"避免覆盖
    - local 模式：直接写到磁盘
    - WebDAV 模式：PUT 到远程
    """
    if folder_type not in ('tender', 'bid'):
        raise HTTPException(400, detail=f'folder_type 必须是 tender 或 bid，收到: {folder_type}')
    if not files or len(files) == 0:
        raise HTTPException(400, detail='未选择文件')

    sub_label = '招标资料' if folder_type == 'tender' else '投标文档'
    cfg = _ensure_config(db)

    # 1. 优先用 project_id 查数据库里真实存的 folder
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

    # 优先级：db_target_dir > 前端传入 > 拼装
    target_dir = db_target_dir or (target_dir or '').strip() or rendered_dir
    overwrite_flag = str(overwrite).lower() in ('1', 'true', 'yes')

    uploaded = []
    failed = []
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    for f in files:
        original = f.filename or f'unknown_{timestamp}'
        safe_name = sanitize_path_segment(original)
        if not safe_name:
            safe_name = f'file_{timestamp}'
        final_name = safe_name
        counter = 1

        try:
            content = await f.read()
            if cfg.mode == StorageMode.local:
                os.makedirs(target_dir, exist_ok=True)
                full_path = os.path.join(target_dir, final_name)
                # overwrite=true 且文件已存在：直接覆盖（删旧写新）
                # overwrite=false 且文件已存在：加 _N 后缀
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
                # WebDAV 模式
                try:
                    from app.services.webdav_client import upload_file, delete_file_webdav, list_files_webdav
                    webdav_target = target_dir if target_dir.startswith('http') else render_subfolder(rendered_root, sub_label)
                    target_url = webdav_target.rstrip('/') + '/' + final_name
                    if not target_url.startswith('http'):
                        target_url = 'http://invalid' + target_url  # 防御
                    overwritten = False
                    # overwrite=true 且远程已有同名文件：先删后传
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
        except Exception as e:
            logger.exception(f"[upload] 写审计失败: {e}")

    # ★关键：上传完成后回写 Project.tender_folder / bid_folder
    # 这样下次 list-files 时直接用 DB 里的真实路径，不会因为模板/创建者变化而错位
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