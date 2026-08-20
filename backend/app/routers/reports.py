"""报表管理
- 摘要: 总项目数/总金额/各状态计数
- 按月: 项目数量 / 金额月度趋势
- 按合作模式/单位/中标状态: 分组
- Excel 导出: 按筛选条件导出明细
权限：与项目同 (normal 仅自己, important 自己+下属, admin 全部)
"""
import io
from datetime import date, datetime
from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from typing import Optional
from app.database import get_db
from app.models import (
    User, UserRole, Project, ApprovalStatus, CooperationMode, WinBidStatus,
    ProjectFollowup, FollowupStage,
)
from app.schemas import FOLLOWUP_STAGE_CHOICES
from app.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["报表管理"])


def _scoped_query(db: Session, current_user: User):
    q = db.query(Project)
    if current_user.role == UserRole.normal:
        q = q.filter(Project.created_by == current_user.id)
    elif current_user.role == UserRole.important:
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        q = q.filter(or_(
            Project.created_by.in_(child_ids),
            Project.approver_id == current_user.id,
        ))
    # admin 和 archive 角色可以查看所有项目
    return q


def _apply_filters(q, keyword: Optional[str], start_date: Optional[str], end_date: Optional[str]):
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            Project.project_name.contains(keyword),
            Project.partner_company.contains(keyword),
            Project.project_code.contains(keyword),
        ))
    if start_date:
        try:
            q = q.filter(Project.tender_time >= date.fromisoformat(start_date))
        except Exception:
            pass
    if end_date:
        try:
            q = q.filter(Project.tender_time <= date.fromisoformat(end_date))
        except Exception:
            pass
    return q


@router.get("/summary")
def summary(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date)
    total = q.count()
    total_amount = q.with_entities(func.coalesce(func.sum(Project.project_amount), 0.0)).scalar() or 0.0
    fee_amount = q.with_entities(func.coalesce(func.sum(Project.fee_amount), 0.0)).scalar() or 0.0
    # 状态分布
    status_rows = q.with_entities(
        Project.approval_status, func.count(Project.id), func.coalesce(func.sum(Project.project_amount), 0.0)
    ).group_by(Project.approval_status).all()
    by_status = []
    for st, cnt, amt in status_rows:
        by_status.append({
            "status": st.value if hasattr(st, 'value') else str(st),
            "count": int(cnt),
            "amount": float(amt),
        })
    return {
        "total": total,
        "total_amount": float(total_amount),
        "fee_amount": float(fee_amount),
        "by_status": by_status,
    }


@router.get("/trend")
def trend(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按投标月份统计项目数 + 金额"""
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date)
    # 按 tender_time 月份分组
    month_expr = func.strftime("%Y-%m", Project.tender_time)
    rows = q.with_entities(
        month_expr.label("month"),
        func.count(Project.id),
        func.coalesce(func.sum(Project.project_amount), 0.0),
    ).group_by("month").order_by("month").all()
    return [
        {"month": m, "count": int(c), "amount": float(a)}
        for m, c, a in rows if m
    ]


@router.get("/by-partner")
def by_partner(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date)
    rows = q.with_entities(
        Project.partner_company,
        func.count(Project.id),
        func.coalesce(func.sum(Project.project_amount), 0.0),
    ).group_by(Project.partner_company).order_by(func.count(Project.id).desc()).limit(limit).all()
    return [
        {"partner": p, "count": int(c), "amount": float(a)}
        for p, c, a in rows
    ]


@router.get("/by-cooperation")
def by_cooperation(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date)
    rows = q.with_entities(
        Project.cooperation_mode,
        func.count(Project.id),
        func.coalesce(func.sum(Project.project_amount), 0.0),
    ).group_by(Project.cooperation_mode).all()
    mode_label = {"long_term": "长期合作", "short_term": "短期合作"}
    return [
        {
            "mode": m.value if hasattr(m, 'value') else str(m),
            "label": mode_label.get(m.value if hasattr(m, 'value') else str(m), str(m)),
            "count": int(c),
            "amount": float(a),
        }
        for m, c, a in rows
    ]


@router.get("/by-win-bid")
def by_win_bid(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date)
    rows = q.with_entities(
        Project.win_bid_status,
        func.count(Project.id),
        func.coalesce(func.sum(Project.project_amount), 0.0),
    ).group_by(Project.win_bid_status).all()
    label = {"yes": "已中标", "no": "未中标", "in_progress": "进行中"}
    return [
        {
            "status": s.value if hasattr(s, 'value') else str(s),
            "label": label.get(s.value if hasattr(s, 'value') else str(s), str(s)),
            "count": int(c),
            "amount": float(a),
        }
        for s, c, a in rows
    ]


@router.get("/by-followup-stage")
def by_followup_stage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """项目跟单 — 各阶段项目数 + 预计成交金额合计。

    金额：每个项目只取最新一次跟单的 expected_amount 之和。
    """
    scoped = _scoped_query(db, current_user).subquery()
    visible_proj_ids = db.query(scoped.c.id).subquery()

    # 项目数（最新跟单在该阶段的项目数）
    sub = db.query(
        ProjectFollowup.project_id,
        func.max(ProjectFollowup.created_at).label('mx'),
    ).filter(
        ProjectFollowup.project_id.in_(visible_proj_ids)
    ).group_by(ProjectFollowup.project_id).subquery()

    latest = db.query(ProjectFollowup).join(
        sub,
        (ProjectFollowup.project_id == sub.c.project_id) &
        (ProjectFollowup.created_at == sub.c.mx),
    ).all()

    stat = {s: {"stage": s, "count": 0, "expected_amount": 0.0} for s in FOLLOWUP_STAGE_CHOICES}
    for it in latest:
        st = it.stage.value if hasattr(it.stage, 'value') else str(it.stage)
        if st not in stat:
            stat[st] = {"stage": st, "count": 0, "expected_amount": 0.0}
        stat[st]["count"] += 1
        stat[st]["expected_amount"] += float(it.expected_amount or 0)

    # 阶段排序按定义顺序
    result = []
    for s in FOLLOWUP_STAGE_CHOICES:
        d = stat[s]
        d["expected_amount"] = round(d["expected_amount"], 2)
        result.append(d)
    return result


@router.get("/export")
def export(
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出当前筛选条件下的项目明细为 Excel"""
    q = _apply_filters(_scoped_query(db, current_user), keyword, start_date, end_date).options(
        joinedload(Project.creator),
        joinedload(Project.approver),
    ).order_by(Project.id.desc())
    rows = q.all()

    # 尝试 openpyxl, 缺失则退 CSV
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "项目明细"
        headers = ["项目编号", "项目名称", "项目类型", "合作单位", "公司地址",
                   "业主联系人", "业主联系方式", "主要资质", "法定代表",
                   "联系人", "联系方式", "合作模式", "费用模式",
                   "项目金额", "费用金额", "是否SM", "中标状态", "审批状态",
                   "招标日期", "投标日期", "创建人", "审批人", "创建时间"]
        ws.append(headers)
        type_label = {"information": "信息化", "intelligent": "智能化", "mep_fire": "机电消防",
                      "software": "软件开放", "ops": "系统运维", "xc_sm": "XC/SM",
                      "military": "军队武警", "other": "其他"}
        coop_label = {"long_term": "长期合作", "short_term": "短期合作"}
        fee_label = {"mutual": "互免", "charged": "收费"}
        sm_label = {"yes": "是", "no": "否"}
        win_label = {"yes": "中标", "no": "未中标", "in_progress": "进行中"}
        status_label = {"pending_submit": "待提交", "pending_approval": "待审批",
                        "approved": "已通过", "rejected": "已驳回"}
        for p in rows:
            project_type_val = p.project_type.value if hasattr(p.project_type, 'value') else p.project_type
            ws.append([
                p.project_code or "",
                p.project_name or "",
                type_label.get(str(project_type_val), str(project_type_val)),
                p.partner_company or "",
                p.company_address or "",
                p.owner_contact_person or "",
                p.owner_contact_info or "",
                p.main_qualification or "",
                p.legal_representative or "",
                p.contact_person or "",
                p.contact_info or "",
                coop_label.get(p.cooperation_mode.value if hasattr(p.cooperation_mode, 'value') else p.cooperation_mode, ""),
                fee_label.get(p.fee_mode.value if hasattr(p.fee_mode, 'value') else p.fee_mode, ""),
                float(p.project_amount or 0),
                float(p.fee_amount or 0),
                sm_label.get(p.is_sm.value if hasattr(p.is_sm, 'value') else p.is_sm, ""),
                win_label.get(p.win_bid_status.value if hasattr(p.win_bid_status, 'value') else p.win_bid_status, ""),
                status_label.get(p.approval_status.value if hasattr(p.approval_status, 'value') else p.approval_status, ""),
                p.tender_time.isoformat() if p.tender_time else "",
                p.bid_time.isoformat() if p.bid_time else "",
                p.creator.real_name if p.creator else "",
                p.approver.real_name if p.approver else "",
                p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
            ])
        # 列宽
        for col, w in enumerate([14, 30, 12, 24, 20, 12, 14, 14, 12, 12, 14, 12, 10, 14, 12, 8, 10, 10, 12, 12, 10, 10, 16], 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        fname = f"projects_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={fname}"},
        )
    except ImportError:
        # fallback CSV
        import csv
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["项目编号", "项目名称", "合作单位", "项目金额", "审批状态"])
        for p in rows:
            w.writerow([p.project_code, p.project_name, p.partner_company,
                        p.project_amount, p.approval_status.value if hasattr(p.approval_status, 'value') else p.approval_status])
        data = buf.getvalue().encode("utf-8-sig")
        fname = f"projects_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={fname}"},
        )