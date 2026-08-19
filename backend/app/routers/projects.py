from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, text, func
from typing import List, Optional
import logging
import traceback
from app.database import get_db
from app.models import User, UserRole, Project, ApprovalLog, ApprovalStatus, ApprovalAction, FileStorageConfig, StorageMode, StorageZone, AuditAction
from app.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ApprovalRequest, ApprovalLogResponse, MessageResponse
)
from app.auth import get_current_user, require_admin, require_important_or_admin, require_not_archive
from app.services.file_storage import create_project_folders
from app.services.audit import write_audit
from datetime import date, datetime
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/api/projects", tags=["项目管理"])
log = logging.getLogger("projects")

def build_project_query(db: Session, current_user: User, filters: dict):
    q = db.query(Project).options(
        joinedload(Project.creator),
        joinedload(Project.approver)
    )
    if current_user.role == UserRole.normal:
        # 普通账号只能看自己的
        q = q.filter(Project.created_by == current_user.id)
    elif current_user.role == UserRole.important:
        # 重要账号：看自己 + 管辖范围内的
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        q = q.filter(or_(
            Project.created_by.in_(child_ids),
            and_(
                Project.approver_id == current_user.id,
                Project.approval_status != ApprovalStatus.pending_submit
            )
        ))
    elif current_user.role == UserRole.archive:
        # 档案管理：看全部项目（只读）
        pass
    # 其他筛选
    if filters.get("project_name"):
        q = q.filter(Project.project_name.contains(filters["project_name"]))
    if filters.get("partner_company"):
        q = q.filter(Project.partner_company.contains(filters["partner_company"]))
    if filters.get("approval_status"):
        q = q.filter(Project.approval_status == filters["approval_status"])
    if filters.get("win_bid_status"):
        q = q.filter(Project.win_bid_status == filters["win_bid_status"])
    if filters.get("start_date"):
        # 填报日期（按 created_at 日期部分筛选）
        q = q.filter(func.date(Project.created_at) >= date.fromisoformat(filters["start_date"]))
    if filters.get("end_date"):
        q = q.filter(func.date(Project.created_at) <= date.fromisoformat(filters["end_date"]))
    if filters.get("min_amount") is not None:
        # 前端传的是万元，乘以 10000 转成元（数据库存的是元）
        q = q.filter(Project.project_amount >= float(filters["min_amount"]) * 10000)
    if filters.get("max_amount") is not None:
        q = q.filter(Project.project_amount <= float(filters["max_amount"]) * 10000)
    if filters.get("source"):
        q = q.filter(Project.source == filters["source"])
    return q

@router.get("", response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_name: Optional[str] = None,
    partner_company: Optional[str] = None,
    approval_status: Optional[str] = None,
    win_bid_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    source: Optional[str] = None,  # channel=渠道项目 / self=自建项目
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filters = {
        "project_name": project_name,
        "partner_company": partner_company,
        "approval_status": approval_status,
        "win_bid_status": win_bid_status,
        "start_date": start_date,
        "end_date": end_date,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "source": source,
    }
    q = build_project_query(db, current_user, filters)
    # 关联加载 creator/approver（前端编辑项目时需要 creator.username/real_name 拼出文件路径）
    q = q.options(joinedload(Project.creator), joinedload(Project.approver))
    total = q.count()
    items = q.order_by(Project.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).options(
        joinedload(Project.creator),
        joinedload(Project.approver)
    ).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限校验
    if current_user.role == UserRole.normal and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此项目")
    if current_user.role == UserRole.important:
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        # 是创建者或下属创建：可以看
        if project.created_by in child_ids:
            pass
        # 是审批人：仅看已提交状态
        elif project.approver_id == current_user.id and project.approval_status != ApprovalStatus.pending_submit:
            pass
        else:
            raise HTTPException(status_code=403, detail="无权查看此项目")
    # archive 角色可以查看所有项目
    return project

@router.post("", response_model=ProjectResponse)
def create_project(
    data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive)
):
    # 必填校验：项目名称
    if not (data.project_name and data.project_name.strip()):
        raise HTTPException(status_code=422, detail="项目名称不能为空")

    # 自动获取审批人：优先使用当前用户的上级（parent_id），没有上级则用系统管理员
    approver_id = None
    if current_user.parent_id:
        approver_id = current_user.parent_id
    else:
        # 兜底：取第一个 admin 作为审批人
        admin_user = db.query(User).filter(User.role == UserRole.admin, User.is_active == True).first()
        if admin_user:
            approver_id = admin_user.id
    if not approver_id:
        raise HTTPException(status_code=422, detail="未找到可用审批人，请在用户管理中为该账号设置上级")

    # 检查编号唯一（空字符串视为 None — 允许多个空项目编号）
        code = (data.project_code or '').strip() or None
        if code:
            existing = db.query(Project).filter(Project.project_code == code).first()
            if existing:
                raise HTTPException(status_code=400, detail="项目编号已存在")
    storage_cfg = db.query(FileStorageConfig).filter(FileStorageConfig.id == 1).first()
    tender_folder = None
    bid_folder = None
    if storage_cfg:
        try:
            folders = create_project_folders(
                db, storage_cfg, current_user.username, current_user.real_name, data.project_name,
                responsible_sales=getattr(data, 'responsible_sales', None)
            )
            tender_folder = folders['tender_folder']
            bid_folder = folders['bid_folder']
            log.warning(f"[create_project] folders ok: tender={tender_folder} bid={bid_folder}")
        except Exception as e:
            # 目录创建失败不阻塞项目创建，但记录警告
            log.error(f"[create_project] 文件夹创建失败: {e}\n{traceback.format_exc()}")

    payload = data.model_dump()
    # 把空字符串规范化成 None（DB 列允许 NULL 的字段）
    for k in ('project_code', 'partner_company', 'owner_contact_person', 'owner_contact_info',
              'company_address', 'main_qualification', 'legal_representative',
              'contact_person', 'contact_info', 'project_overview', 'tender_file', 'bid_file'):
        if payload.get(k) in ('', None):
            payload[k] = None

    # 使用自动获取的审批人，创建后直接进入"待审批"状态
    initial_status = ApprovalStatus.pending_approval

    # 用自动获取的审批人覆盖表单中的 approver_id
    payload['approver_id'] = approver_id

    project = Project(
        **payload,
        created_by=current_user.id,
        tender_folder=tender_folder,
        bid_folder=bid_folder,
        approval_status=initial_status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    write_audit(
        current_user, AuditAction.project_create,
        target_type='project', target_id=project.id, target_name=project.project_name,
        details={'project_type': data.project_type.value if hasattr(data.project_type, 'value') else str(data.project_type),
                 'tender_folder': tender_folder, 'bid_folder': bid_folder,
                 'expected_amount': data.expected_amount, 'cooperation_mode': str(data.cooperation_mode),
                 'initial_status': initial_status.value},
        request=request,
    )
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限：普通账号可以编辑任何项目（用于上传文件），但不能编辑"已通过"的项目
    if current_user.role == UserRole.normal:
        if project.approval_status == ApprovalStatus.approved.value:
            raise HTTPException(status_code=400, detail="已通过的项目不可编辑")
    
    # 管理员权限控制：
    # 1. admin 可以修改 win_bid_status 字段
    # 2. 非 admin 角色修改 win_bid_status 会被忽略
    is_admin = current_user.role == UserRole.admin
    
    # 获取允许更新的字段（先把验证专用字段提出来，不要进入 setattr 循环）
    raw_data = data.model_dump(exclude_unset=True)
    win_bid_change_reason = raw_data.pop('win_bid_change_reason', None)
    admin_password_verify = raw_data.pop('admin_password_verify', None)
    update_data = raw_data
    
    # 非管理员不能修改 win_bid_status
    if not is_admin and 'win_bid_status' in update_data:
        del update_data['win_bid_status']

    # 中标状态修改权限校验：
    # - 首次修改（win_bid_status_set_at is None）：admin 可直接改
    # - 非首次修改（win_bid_status_set_at is not None）：admin 必须提供「修改理由」+「密码验证」
    if 'win_bid_status' in update_data and project.win_bid_status_set_at is not None:
        if not is_admin:
            raise HTTPException(status_code=400, detail="中标状态已锁定，不允许再次修改")
        # 非首次修改：要求理由 + 密码
        if not win_bid_change_reason or not str(win_bid_change_reason).strip():
            raise HTTPException(status_code=400, detail="非首次修改中标状态必须填写修改理由")
        if not admin_password_verify:
            raise HTTPException(status_code=400, detail="非首次修改中标状态必须验证管理员密码")
        # 验证管理员密码
        from app.auth import verify_password
        if not verify_password(admin_password_verify, current_user.password_hash):
            raise HTTPException(status_code=400, detail="管理员密码验证失败")
    
    # 如果没有可更新的字段，返回当前项目
    if not update_data:
        return project
    
    # 记录变更
    changes = {}
    for field, value in update_data.items():
        old_val = getattr(project, field, None)
        if old_val != value:
            changes[field] = {'old': str(old_val) if old_val is not None else None,
                              'new': str(value) if value is not None else None}
        setattr(project, field, value)
    # 第一次设置中标状态时记录时间戳（用于判定"是否首次"）
    if 'win_bid_status' in update_data and project.win_bid_status_set_at is None:
        project.win_bid_status_set_at = datetime.now(ZoneInfo('Asia/Shanghai'))
        changes['win_bid_status_set_at'] = {'old': None, 'new': str(project.win_bid_status_set_at)}
    # 非首次修改中标状态：把理由一并写入审计
    if 'win_bid_status' in update_data and win_bid_change_reason:
        changes['win_bid_change_reason'] = str(win_bid_change_reason).strip()
    db.commit()
    db.refresh(project)
    if changes:
        write_audit(
            current_user, AuditAction.project_update,
            target_type='project', target_id=project.id, target_name=project.project_name,
            details=changes, request=request,
        )
    return project

def _resolve_db_path() -> str:
    from app.database import load_config
    cfg = load_config()
    raw = cfg["database"]["url"].replace("sqlite:///", "", 1)
    if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
        raw = raw[1:]
    return raw


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(
    project_id: int,
    # 故意不要 db 依赖，避免 SA 持锁导致后续 sqlite3 写入失败
    current_user: User = Depends(require_not_archive)
):
    log.warning(f"[delete_project] start id={project_id} user={current_user.id} role={current_user.role}")
    import sqlite3 as _sqlite3
    import time as _time

    def _do_delete():
        path = _resolve_db_path()
        log.warning(f"[delete_project] db path={path}")
        # 退避重试：解决 SA 残留锁的问题
        for attempt in range(5):
            c = _sqlite3.connect(path, timeout=30, check_same_thread=False)
            try:
                c.execute("PRAGMA busy_timeout=30000")
                c.execute("PRAGMA journal_mode=MEMORY")
                c.execute("PRAGMA locking_mode=EXCLUSIVE")
                row = c.execute("SELECT created_by, approval_status, project_name FROM projects WHERE id = ?", (project_id,)).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="项目不存在")
                created_by, approval_status, project_name = row
                
                # 权限控制：
                # 1. admin 角色可以删除任何项目
                # 2. 其他角色只能删除自己创建的、待提交状态的项目
                is_admin = current_user.role == UserRole.admin
                if not is_admin:
                    if created_by != current_user.id:
                        raise HTTPException(status_code=403, detail="无权删除此项目")
                    if approval_status != ApprovalStatus.pending_submit.value:
                        raise HTTPException(status_code=400, detail="仅待提交状态可删除")
                c.execute("DELETE FROM approval_logs WHERE project_id = ?", (project_id,))
                cur = c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                c.commit()
                log.warning(f"[delete_project] rowcount={cur.rowcount} attempt={attempt}")
                return cur.rowcount
            except _sqlite3.OperationalError as e:
                if "locked" in str(e) or "I/O" in str(e):
                    log.warning(f"[delete_project] retry attempt={attempt} err={e}")
                    _time.sleep(0.5)
                    continue
                raise
            finally:
                try:
                    c.close()
                except Exception:
                    pass
        raise HTTPException(status_code=503, detail="数据库暂时不可用，请重试")

    try:
        result = _do_delete()
        log.warning(f"[delete_project] ok id={project_id} result={result}")
        # 审计
        try:
            write_audit(
                current_user, AuditAction.project_delete,
                target_type='project', target_id=project_id, target_name=project_name,
                request=request,
            )
        except Exception:
            pass
        return MessageResponse(message="项目已删除")
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[delete_project] error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")

@router.post("/{project_id}/submit", response_model=ProjectResponse)
def submit_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.created_by != current_user.id and current_user.role == UserRole.normal:
        raise HTTPException(status_code=403, detail="无权提交此项目")
    if project.approval_status != ApprovalStatus.pending_submit.value:
        raise HTTPException(status_code=400, detail="只能提交待提交状态的项目")
    if not project.approver_id:
        raise HTTPException(status_code=400, detail="请先指定审批人")
    project.approval_status = ApprovalStatus.pending_approval
    log = ApprovalLog(
        project_id=project_id,
        approver_id=current_user.id,
        action=ApprovalAction.submit,
        comment='创建者提交审批',
    )
    db.add(log)
    db.commit()
    db.refresh(project)
    write_audit(
        current_user, AuditAction.project_submit,
        target_type='project', target_id=project.id, target_name=project.project_name,
        request=request,
    )
    return project

@router.post("/{project_id}/approve", response_model=ProjectResponse)
def approve_project(
    project_id: int,
    data: ApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限检查：admin 可审批任何项目，其他角色仅指定审批人可审批
    if current_user.role != UserRole.admin and project.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权审批此项目")
    if project.approval_status != ApprovalStatus.pending_approval.value:
        raise HTTPException(status_code=400, detail="只能审批待审批状态的项目")
    project.approval_status = ApprovalStatus.approved
    log = ApprovalLog(
        project_id=project_id,
        approver_id=current_user.id,
        action=ApprovalAction.approve,
        comment=data.comment
    )
    db.add(log)
    db.commit()
    db.refresh(project)
    write_audit(
        current_user, AuditAction.project_approve,
        target_type='project', target_id=project.id, target_name=project.project_name,
        details={'comment': data.comment}, request=request,
    )
    return project


@router.post("/{project_id}/reject", response_model=ProjectResponse)
def reject_project(
    project_id: int,
    data: ApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_not_archive)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限检查：admin 可审批任何项目，其他角色仅指定审批人可审批
    if current_user.role != UserRole.admin and project.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权审批此项目")
    if project.approval_status != ApprovalStatus.pending_approval.value:
        raise HTTPException(status_code=400, detail="只能驳回待审批状态的项目")
    project.approval_status = ApprovalStatus.rejected
    log = ApprovalLog(
        project_id=project_id,
        approver_id=current_user.id,
        action=ApprovalAction.reject,
        comment=data.comment
    )
    db.add(log)
    db.commit()
    db.refresh(project)
    write_audit(
        current_user, AuditAction.project_reject,
        target_type='project', target_id=project.id, target_name=project.project_name,
        details={'comment': data.comment}, request=request,
    )
    return project

@router.post("/{project_id}/withdraw", response_model=ProjectResponse)
def withdraw_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    撤回项目：创建者把项目从"待审批"或"已驳回"撤回到"待提交"状态。
    - 仅项目创建者可撤回
    - 仅在 pending_approval / rejected 状态下可撤回（pending_submit 无需撤回）
    - 不删除 NAS 上已存在的项目目录和文件
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 仅创建者可撤回
    if project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="只有项目创建者可以撤回")
    # 仅在待审批/已驳回状态可撤回
    withdrawable_states = [ApprovalStatus.pending_approval.value, ApprovalStatus.rejected.value]
    if project.approval_status not in withdrawable_states:
        raise HTTPException(status_code=400, detail=f"当前状态({project.approval_status})不支持撤回")
    previous_status = project.approval_status
    project.approval_status = ApprovalStatus.pending_submit
    log = ApprovalLog(
        project_id=project_id,
        approver_id=current_user.id,
        action=ApprovalAction.withdraw,
        comment=f"创建者撤回（之前状态: {previous_status}）"
    )
    db.add(log)
    db.commit()
    db.refresh(project)
    write_audit(
        current_user, AuditAction.project_withdraw,
        target_type='project', target_id=project.id, target_name=project.project_name,
        details={'previous_status': previous_status}, request=request,
    )
    return project


@router.get("/{project_id}/logs", response_model=List[ApprovalLogResponse])
def get_approval_logs(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logs = db.query(ApprovalLog).options(
        joinedload(ApprovalLog.approver_user)
    ).filter(ApprovalLog.project_id == project_id).order_by(ApprovalLog.created_at).all()
    return logs
