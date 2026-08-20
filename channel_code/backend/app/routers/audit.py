"""审计日志 API - 列表、搜索、导出"""
import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User, UserRole
from app.schemas import AuditLogResponse, AuditLogListResponse
from app.auth import require_manager

log = logging.getLogger("audit_api")

router = APIRouter(prefix="/api/audit", tags=["审计记录"])


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """审计日志列表（管理员/重要管理员可访问）"""
    q = db.query(AuditLog)
    if action:
        # 支持前缀匹配：user.* 可匹配所有用户操作
        if action.endswith('*'):
            q = q.filter(AuditLog.action.like(action[:-1] + '%'))
        else:
            q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if username:
        q = q.filter(AuditLog.username.contains(username))
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date)
            q = q.filter(AuditLog.created_at >= dt)
        except ValueError:
            raise HTTPException(400, detail="start_date 格式错误，应为 YYYY-MM-DD")
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date)
            q = q.filter(AuditLog.created_at <= dt)
        except ValueError:
            raise HTTPException(400, detail="end_date 格式错误，应为 YYYY-MM-DD")

    # 重要管理员只能看到自己 + 下属的操作
    if current_user.role == UserRole.important_admin:
        from sqlalchemy import or_
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        q = q.filter(or_(AuditLog.user_id.in_(child_ids), AuditLog.user_id == None))

    total = q.count()
    items = q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
def export_audit_logs(
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """导出审计日志为 CSV"""
    q = db.query(AuditLog)
    if action:
        if action.endswith('*'):
            q = q.filter(AuditLog.action.like(action[:-1] + '%'))
        else:
            q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if username:
        q = q.filter(AuditLog.username.contains(username))
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date)
            q = q.filter(AuditLog.created_at >= dt)
        except ValueError:
            pass
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date)
            q = q.filter(AuditLog.created_at <= dt)
        except ValueError:
            pass

    if current_user.role == UserRole.important_admin:
        from sqlalchemy import or_
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        q = q.filter(or_(AuditLog.user_id.in_(child_ids), AuditLog.user_id == None))

    items = q.order_by(AuditLog.id.desc()).limit(10000).all()

    # 生成 CSV
    output = io.StringIO()
    # 写 BOM 以让 Excel 正确识别 UTF-8
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['ID', '时间', '操作人', '姓名', '角色', '操作类型', '对象类型', '对象ID', '对象名称', '详情', 'IP地址'])
    ROLE_LABELS = {
        'admin': '系统管理员',
        'important_admin': '重要管理员',
        'important': '重要账号',
        'normal': '普通账号',
    }
    for it in items:
        writer.writerow([
            it.id,
            it.created_at.strftime('%Y-%m-%d %H:%M:%S') if it.created_at else '',
            it.username,
            it.real_name or '',
            ROLE_LABELS.get(it.role, it.role or ''),
            it.action,
            it.target_type or '',
            it.target_id or '',
            it.target_name or '',
            it.details or '',
            it.ip_address or '',
        ])

    output.seek(0)
    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type='text/csv',
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
