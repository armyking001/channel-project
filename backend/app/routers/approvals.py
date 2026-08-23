"""审批管理路由
- 待审批列表 (pending): 当前用户作为审批人的待审批项目
- 已审批列表 (history): 当前用户已处理过的项目 (含 approve/reject)
- 范围内: 我能审批的总览
权限规则：
  admin: 待审批=全部 pending_approval; 已审批=全部已结项目（approved/rejected）
  important: 待审批=approver_id=我 或 下属创建的 + pending_approval; 已审批=我操作过的日志
  normal: 仅查看自己已审批的日志 (一般没有, 但不能完全隐藏入口, 给只读)
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from typing import Optional
from app.database import get_db
from app.models import (
    User, UserRole, Project, ApprovalLog, ApprovalStatus, ApprovalAction
)
from app.schemas import ProjectListResponse, MessageResponse
from app.auth import get_current_user, require_not_archive

router = APIRouter(prefix="/api/approvals", tags=["审批管理"])


def _scope_project_ids(db: Session, current_user: User, pending_only: bool = False):
    """计算当前用户在审批场景下"能看到的项目集"。

    pending_only=True:  限制为 pending_approval 状态
    pending_only=False: 不限状态
    """
    q = db.query(Project)
    if current_user.role == UserRole.admin:
        pass  # 管理员看全部
    elif current_user.role == UserRole.archive:
        # 档案管理：看全部已审批和待审批项目（不含待提交）
        q = q.filter(Project.approval_status != ApprovalStatus.pending_submit)
    elif current_user.role == UserRole.important:
        # 自己管辖的下属 id 集合 + 自己
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        # 创建人在 child_ids 内, 或者是 approver=我
        q = q.filter(or_(
            Project.created_by.in_(child_ids),
            Project.approver_id == current_user.id,
        ))
    else:
        # 普通账号: 看不到自己没创建的；只能看到自己被指定为审批人的项目
        q = q.filter(Project.approver_id == current_user.id)

    if pending_only:
        q = q.filter(Project.approval_status == ApprovalStatus.pending_approval)
    return q


@router.get("/pending", response_model=ProjectListResponse)
def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_name: Optional[str] = None,
    responsible_sales: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """待审批项目列表。"""
    q = _scope_project_ids(db, current_user, pending_only=True).options(
        joinedload(Project.creator),
        joinedload(Project.approver),
    )
    if project_name:
        q = q.filter(Project.project_name.contains(project_name))
    if responsible_sales:
        q = q.filter(Project.responsible_sales.contains(responsible_sales))

    total = q.count()
    items = q.order_by(Project.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/history", response_model=ProjectListResponse)
def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_name: Optional[str] = None,
    responsible_sales: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """已审批列表：当前用户操作过 (approve/reject) 的项目。"""
    sub = db.query(ApprovalLog.project_id).filter(ApprovalLog.approver_id == current_user.id).subquery()
    q = db.query(Project).filter(Project.id.in_(sub)).options(
        joinedload(Project.creator),
        joinedload(Project.approver),
    )
    if project_name:
        q = q.filter(Project.project_name.contains(project_name))
    if responsible_sales:
        q = q.filter(Project.responsible_sales.contains(responsible_sales))

    total = q.count()
    items = q.order_by(Project.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/summary", response_model=MessageResponse)
def approvals_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """头部 KPI：返回当前用户视角的待审批 / 已审批 / 范围内总数。"""
    pending_q = _scope_project_ids(db, current_user, pending_only=True)
    pending_count = pending_q.count()

    sub = db.query(ApprovalLog.project_id).filter(ApprovalLog.approver_id == current_user.id).subquery()
    history_count = db.query(Project).filter(Project.id.in_(sub)).count()

    scope_q = _scope_project_ids(db, current_user, pending_only=False)
    scope_count = scope_q.count()

    return MessageResponse(
        message=f"pending={pending_count}|history={history_count}|scope={scope_count}|role={current_user.role.value}",
    )


@router.post("/{project_id}/approve", response_model=MessageResponse)
def approve(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_not_archive), request: Request = None):
    from fastapi import HTTPException
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限检查：admin 可审批任何项目，其他角色仅指定审批人可审批
    if current_user.role != UserRole.admin and project.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权审批此项目")
    if project.approval_status != ApprovalStatus.pending_approval:
        raise HTTPException(status_code=400, detail="项目当前不在待审批状态")
    project.approval_status = ApprovalStatus.approved
    db.add(ApprovalLog(project_id=project_id, approver_id=current_user.id,
                       action=ApprovalAction.approve))
    db.commit()
    from app.services.audit import write_audit, AuditAction
    write_audit(current_user, AuditAction.project_approve,
                target_type='project', target_id=project.id, target_name=project.project_name,
                details={}, request=request)
    # 通知项目创建人
    try:
        if project.created_by and project.created_by != current_user.id:
            from app.services.notifications import send_notification
            from app.models import NotificationType
            send_notification(
                db,
                receiver_id=project.created_by,
                type=NotificationType.project_approved,
                title="项目审批通过",
                content="您提交的项目「{0}」已被 {1} 通过。".format(
                    project.project_name,
                    current_user.real_name or current_user.username,
                ),
                target_type="project", target_id=project.id,
            )
            db.commit()
    except Exception:
        pass
    return MessageResponse(message="已通过")


@router.post("/{project_id}/reject", response_model=MessageResponse)
def reject(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_not_archive), request: Request = None):
    from fastapi import HTTPException
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 权限检查：admin 可审批任何项目，其他角色仅指定审批人可审批
    if current_user.role != UserRole.admin and project.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权审批此项目")
    if project.approval_status != ApprovalStatus.pending_approval:
        raise HTTPException(status_code=400, detail="项目当前不在待审批状态")
    project.approval_status = ApprovalStatus.rejected
    db.add(ApprovalLog(project_id=project_id, approver_id=current_user.id,
                       action=ApprovalAction.reject))
    db.commit()
    from app.services.audit import write_audit, AuditAction
    write_audit(current_user, AuditAction.project_reject,
                target_type='project', target_id=project.id, target_name=project.project_name,
                details={}, request=request)
    # 通知项目创建人
    try:
        if project.created_by and project.created_by != current_user.id:
            from app.services.notifications import send_notification
            from app.models import NotificationType
            send_notification(
                db,
                receiver_id=project.created_by,
                type=NotificationType.project_rejected,
                title="项目审批驳回",
                content="您提交的项目「{0}」已被 {1} 驳回,请查看详情。".format(
                    project.project_name,
                    current_user.real_name or current_user.username,
                ),
                target_type="project", target_id=project.id,
            )
            db.commit()
    except Exception:
        pass
    return MessageResponse(message="已驳回")
