"""财务催款路由 — 8 个核心接口

POST   /api/finance/receivables/import     上传 Excel 导入应收表
POST   /api/finance/trust/import            上传 Excel 导入信托表
GET    /api/finance/receivables             分页查询
GET    /api/finance/trust                   分页查询
GET    /api/finance/persons                 去重的待催人员列表
POST   /api/finance/reminder/send           触发发送(指定人/全部)
PUT    /api/finance/receivables/{id}/frequency  更新应收记录频率
PUT    /api/finance/trust/{id}/frequency        更新信托记录频率
GET    /api/finance/reminder/logs               发送日志查询(辅助)
"""
import io
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_finance_or_admin
from app.database import get_db
from app.models import (
    FinanceReceivable, FinanceTrust, FinanceReminderLog, User,
)
from app.services.finance_excel import (
    import_receivables, import_trust, send_sms_for_record,
)

log = logging.getLogger("finance_router")
router = APIRouter(prefix="/api/finance", tags=["finance"])


# ============ 导入 ============

@router.post("/receivables/import")
async def api_import_receivables(
    file: UploadFile = File(...),
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    try:
        content = await file.read()
        result = import_receivables(db, content, file.filename or "receivables.xlsx")
        return result
    except Exception as e:
        log.exception("import receivables failed")
        raise HTTPException(status_code=400, detail=f"导入失败: {e}")


@router.post("/trust/import")
async def api_import_trust(
    file: UploadFile = File(...),
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    try:
        content = await file.read()
        result = import_trust(db, content, file.filename or "trust.xlsx")
        return result
    except Exception as e:
        log.exception("import trust failed")
        raise HTTPException(status_code=400, detail=f"导入失败: {e}")


# ============ 列表查询 ============

def _paginate(db: Session, model, page: int, page_size: int, q: Optional[str]):
    query = db.query(model)
    if q:
        like = f"%{q}%"
        if model is FinanceReceivable:
            query = query.filter(or_(
                model.contract_no.like(like),
                model.project_name.like(like),
                model.customer.like(like),
                model.sales_person.like(like),
                model.engineer.like(like),
                model.phone.like(like),
            ))
        else:
            query = query.filter(or_(
                model.subject_name.like(like),
                model.employee.like(like),
                model.owner.like(like),
                model.phone.like(like),
                model.category.like(like),
                model.company.like(like),
                model.department.like(like),
            ))
    total = query.count()
    items = query.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def _serialize_receivable(r: FinanceReceivable) -> dict:
    return {
        "id": r.id, "batch_id": r.batch_id,
        "contract_no": r.contract_no, "project_name": r.project_name,
        "customer": r.customer, "amount": r.amount,
        "sales_person": r.sales_person, "engineer": r.engineer,
        "phone": r.phone,
        "plan_date": r.plan_date.isoformat() if r.plan_date else None,
        "remind_start_at": r.remind_start_at.isoformat() if r.remind_start_at else None,
        "remind_end_at": r.remind_end_at.isoformat() if r.remind_end_at else None,
        "frequency": r.frequency, "reminder_count": r.reminder_count,
        "last_reminder_at": r.last_reminder_at.isoformat() if r.last_reminder_at else None,
        "last_status": r.last_status, "remark": r.remark,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _serialize_trust(r: FinanceTrust) -> dict:
    return {
        "id": r.id, "batch_id": r.batch_id,
        "subject_name": r.subject_name, "balance": r.balance, "category": r.category,
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
        "company": r.company, "department": r.department, "employee": r.employee,
        "phone": r.phone, "owner": r.owner,
        "plan_repay_date": r.plan_repay_date.isoformat() if r.plan_repay_date else None,
        "remind_start_at": r.remind_start_at.isoformat() if r.remind_start_at else None,
        "remind_end_at": r.remind_end_at.isoformat() if r.remind_end_at else None,
        "frequency": r.frequency, "reminder_count": r.reminder_count,
        "last_reminder_at": r.last_reminder_at.isoformat() if r.last_reminder_at else None,
        "last_status": r.last_status, "remark": r.remark,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/receivables")
def api_list_receivables(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = None, batch_id: Optional[str] = None,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    query = db.query(FinanceReceivable)
    if batch_id:
        query = query.filter(FinanceReceivable.batch_id == batch_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            FinanceReceivable.contract_no.like(like),
            FinanceReceivable.project_name.like(like),
            FinanceReceivable.customer.like(like),
            FinanceReceivable.sales_person.like(like),
            FinanceReceivable.engineer.like(like),
            FinanceReceivable.phone.like(like),
        ))
    total = query.count()
    items = query.order_by(FinanceReceivable.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize_receivable(r) for r in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/trust")
def api_list_trust(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = None, batch_id: Optional[str] = None,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    query = db.query(FinanceTrust)
    if batch_id:
        query = query.filter(FinanceTrust.batch_id == batch_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            FinanceTrust.subject_name.like(like),
            FinanceTrust.employee.like(like),
            FinanceTrust.owner.like(like),
            FinanceTrust.phone.like(like),
            FinanceTrust.category.like(like),
            FinanceTrust.company.like(like),
            FinanceTrust.department.like(like),
        ))
    total = query.count()
    items = query.order_by(FinanceTrust.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize_trust(r) for r in items],
        "total": total, "page": page, "page_size": page_size,
    }


# ============ 人员(去重) ============

@router.get("/persons")
def api_list_persons(
    type: str = Query("receivables", pattern="^(receivables|trust)$"),
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """返回 (name, phone) 列表, 给前端'选择某人'下拉框用"""
    persons: List[dict] = []
    seen = set()
    if type == "receivables":
        rows = db.query(
            FinanceReceivable.sales_person, FinanceReceivable.engineer,
            FinanceReceivable.phone, FinanceReceivable.customer, FinanceReceivable.id,
        ).all()
        for r in rows:
            name = r.sales_person or r.engineer or r.customer
            if name and r.phone and (name, r.phone) not in seen:
                persons.append({"name": name, "phone": r.phone, "record_id": r.id})
                seen.add((name, r.phone))
    else:
        rows = db.query(
            FinanceTrust.employee, FinanceTrust.owner, FinanceTrust.phone, FinanceTrust.id,
        ).all()
        for r in rows:
            name = r.employee or r.owner
            if name and r.phone and (name, r.phone) not in seen:
                persons.append({"name": name, "phone": r.phone, "record_id": r.id})
                seen.add((name, r.phone))
    return {"items": persons, "total": len(persons)}


# ============ 发送短信 ============

@router.post("/reminder/send")
def api_send_reminder(
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """触发发送:
    payload: {
      record_type: 'receivables'|'trust',
      person_name?: '张三' (指定单人)  /  不传 = 全部
      record_ids?: [1,2,3] (精确到记录,优先级高于 person_name)
      frequency: 'once'|'daily'|'weekly'|'monthly' (本次发送的频率快照)
    }
    返回: {success, sent, failed, skipped, no_channel, warning?, items: [...]}
    """
    record_type = (payload.get("record_type") or "").strip()
    if record_type not in ("receivables", "trust"):
        raise HTTPException(status_code=400, detail="record_type 必须为 receivables 或 trust")
    person_name = (payload.get("person_name") or "").strip()
    record_ids = payload.get("record_ids") or []
    frequency = (payload.get("frequency") or "once").strip()
    channels = payload.get("channels") or None  # 本次允许的通道顺序

    Model = FinanceReceivable if record_type == "receivables" else FinanceTrust
    q = db.query(Model)

    if record_ids:
        q = q.filter(Model.id.in_(record_ids))
    elif person_name:
        if record_type == "receivables":
            q = q.filter(or_(
                FinanceReceivable.sales_person == person_name,
                FinanceReceivable.engineer == person_name,
                FinanceReceivable.customer == person_name,
            ))
        else:
            q = q.filter(or_(
                FinanceTrust.employee == person_name,
                FinanceTrust.owner == person_name,
            ))
    # else: 全部(全量页)

    records = q.all()
    if not records:
        return {"success": True, "sent": 0, "failed": 0, "skipped": 0, "no_channel": 0, "items": []}

    sent = failed = skipped = no_channel = 0
    warning_msg = None
    items = []
    for rec in records:
        try:
            res = send_sms_for_record(db, record_type, rec, frequency, current_user, channels=channels)
            if res["status"] == "sent":
                sent += 1
            elif res["status"] == "skipped":
                skipped += 1
            else:
                # failed 包含原 no_channel(没有可用通道也是失败)
                if res.get("channel") is None and "通道" in (res.get("error") or ""):
                    no_channel += 1
                    if not warning_msg:
                        warning_msg = "未配置已启用的通道,无法发送,请先在'通知管理'中配置"
                else:
                    failed += 1
            items.append({
                "record_id": rec.id,
                "phone": getattr(rec, "phone", None),
                "status": res["status"],
                "error": res.get("error"),
                "channel": res.get("channel"),
            })
        except Exception as e:
            log.exception("send reminder failed for record_id=%s", rec.id)
            failed += 1
            items.append({"record_id": rec.id, "status": "failed", "error": str(e)[:200], "channel": None})

    out = {
        "success": True,
        "record_type": record_type,
        "target_count": len(records),
        "sent": sent, "failed": failed, "skipped": skipped, "no_channel": no_channel,
        "items": items,
    }
    if warning_msg:
        out["warning"] = warning_msg
    return out


# ============ 频率更新 ============

@router.put("/receivables/{rid}/frequency")
def api_update_receivable_frequency(
    rid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    freq = (payload.get("frequency") or "").strip()
    if freq not in ("once", "daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="frequency 必须为 once/daily/weekly/monthly")
    rec = db.query(FinanceReceivable).filter(FinanceReceivable.id == rid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    rec.frequency = freq
    db.commit()
    return {"success": True, "id": rid, "frequency": freq}


@router.put("/trust/{tid}/frequency")
def api_update_trust_frequency(
    tid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    freq = (payload.get("frequency") or "").strip()
    if freq not in ("once", "daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="frequency 必须为 once/daily/weekly/monthly")
    rec = db.query(FinanceTrust).filter(FinanceTrust.id == tid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    rec.frequency = freq
    db.commit()
    return {"success": True, "id": tid, "frequency": freq}


# ============ 提醒结束时间更新 ============

@router.put("/receivables/{rid}/remind-start")
def api_update_receivable_remind_start(
    rid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """更新应收记录的提醒启动时间(含时分)"""
    rec = db.query(FinanceReceivable).filter(FinanceReceivable.id == rid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    raw = payload.get("remind_start_at")
    if raw in (None, "", "null"):
        rec.remind_start_at = None
    else:
        rec.remind_start_at = _parse_iso_datetime(raw)
        if rec.remind_start_at is None:
            raise HTTPException(status_code=400, detail=f"无法解析时间: {raw!r}")
    db.commit()
    return {"success": True, "id": rid, "remind_start_at": rec.remind_start_at.isoformat() if rec.remind_start_at else None}


@router.put("/trust/{tid}/remind-start")
def api_update_trust_remind_start(
    tid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """更新财务借支记录的提醒启动时间"""
    rec = db.query(FinanceTrust).filter(FinanceTrust.id == tid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    raw = payload.get("remind_start_at")
    if raw in (None, "", "null"):
        rec.remind_start_at = None
    else:
        rec.remind_start_at = _parse_iso_datetime(raw)
        if rec.remind_start_at is None:
            raise HTTPException(status_code=400, detail=f"无法解析时间: {raw!r}")
    db.commit()
    return {"success": True, "id": tid, "remind_start_at": rec.remind_start_at.isoformat() if rec.remind_start_at else None}


@router.put("/receivables/{rid}/remind-end")
def api_update_receivable_remind_end(
    rid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """更新应收记录的提醒结束时间(传 null 或空字符串可清空)
    payload: { remind_end_at: "2026-12-31T18:00" | "2026-12-31 18:00:00" | null }
    """
    rec = db.query(FinanceReceivable).filter(FinanceReceivable.id == rid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    raw = payload.get("remind_end_at")
    if raw in (None, "", "null"):
        rec.remind_end_at = None
    else:
        rec.remind_end_at = _parse_iso_datetime(raw)
        if rec.remind_end_at is None:
            raise HTTPException(status_code=400, detail=f"无法解析时间: {raw!r}")
    db.commit()
    return {"success": True, "id": rid, "remind_end_at": rec.remind_end_at.isoformat() if rec.remind_end_at else None}


@router.put("/trust/{tid}/remind-end")
def api_update_trust_remind_end(
    tid: int,
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """更新财务借支记录的提醒结束时间"""
    rec = db.query(FinanceTrust).filter(FinanceTrust.id == tid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    raw = payload.get("remind_end_at")
    if raw in (None, "", "null"):
        rec.remind_end_at = None
    else:
        rec.remind_end_at = _parse_iso_datetime(raw)
        if rec.remind_end_at is None:
            raise HTTPException(status_code=400, detail=f"无法解析时间: {raw!r}")
    db.commit()
    return {"success": True, "id": tid, "remind_end_at": rec.remind_end_at.isoformat() if rec.remind_end_at else None}


def _parse_iso_datetime(s: str):
    """解析 ISO 时间字符串: '2026-12-31T18:00' / '2026-12-31 18:00:00' / '2026-12-31T18:00:00'"""
    from datetime import datetime
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


# ============ 删除(单条 / 批量) ============

@router.delete("/receivables/{rid}")
def api_delete_receivable(
    rid: int,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """删除单条应收记录(同时删除该记录的发送日志)"""
    rec = db.query(FinanceReceivable).filter(FinanceReceivable.id == rid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.query(FinanceReminderLog).filter(
        FinanceReminderLog.record_type == "receivables",
        FinanceReminderLog.record_id == rid,
    ).delete(synchronize_session=False)
    db.delete(rec)
    db.commit()
    return {"success": True, "deleted_id": rid}


@router.delete("/receivables")
def api_delete_receivables_bulk(
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """批量删除应收记录
    payload: { ids: [1, 2, 3] }  - 按 id 精确删除
           | { batch_id: 'xxx' } - 删除整个导入批次
    """
    ids = payload.get("ids") or []
    batch_id = (payload.get("batch_id") or "").strip()
    q = db.query(FinanceReceivable)
    if ids:
        if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
            raise HTTPException(status_code=400, detail="ids 必须是整数数组")
        q = q.filter(FinanceReceivable.id.in_(ids))
    elif batch_id:
        q = q.filter(FinanceReceivable.batch_id == batch_id)
    else:
        raise HTTPException(status_code=400, detail="ids 或 batch_id 至少传一个")
    rows = q.all()
    rid_list = [r.id for r in rows]
    if rid_list:
        db.query(FinanceReminderLog).filter(
            FinanceReminderLog.record_type == "receivables",
            FinanceReminderLog.record_id.in_(rid_list),
        ).delete(synchronize_session=False)
        for r in rows:
            db.delete(r)
        db.commit()
    return {"success": True, "deleted_count": len(rid_list), "deleted_ids": rid_list}


@router.delete("/trust/{tid}")
def api_delete_trust(
    tid: int,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """删除单条财务借支记录"""
    rec = db.query(FinanceTrust).filter(FinanceTrust.id == tid).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.query(FinanceReminderLog).filter(
        FinanceReminderLog.record_type == "trust",
        FinanceReminderLog.record_id == tid,
    ).delete(synchronize_session=False)
    db.delete(rec)
    db.commit()
    return {"success": True, "deleted_id": tid}


@router.delete("/trust")
def api_delete_trust_bulk(
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """批量删除财务借支记录"""
    ids = payload.get("ids") or []
    batch_id = (payload.get("batch_id") or "").strip()
    q = db.query(FinanceTrust)
    if ids:
        if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
            raise HTTPException(status_code=400, detail="ids 必须是整数数组")
        q = q.filter(FinanceTrust.id.in_(ids))
    elif batch_id:
        q = q.filter(FinanceTrust.batch_id == batch_id)
    else:
        raise HTTPException(status_code=400, detail="ids 或 batch_id 至少传一个")
    rows = q.all()
    tid_list = [r.id for r in rows]
    if tid_list:
        db.query(FinanceReminderLog).filter(
            FinanceReminderLog.record_type == "trust",
            FinanceReminderLog.record_id.in_(tid_list),
        ).delete(synchronize_session=False)
        for r in rows:
            db.delete(r)
        db.commit()
    return {"success": True, "deleted_count": len(tid_list), "deleted_ids": tid_list}


# ============ 发送日志查询(辅助) ============

@router.get("/reminder/logs")
def api_list_reminder_logs(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    record_type: Optional[str] = None, status: Optional[str] = None,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    q = db.query(FinanceReminderLog)
    if record_type:
        q = q.filter(FinanceReminderLog.record_type == record_type)
    if status:
        q = q.filter(FinanceReminderLog.status == status)
    total = q.count()
    items = q.order_by(FinanceReminderLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{
            "id": x.id, "record_type": x.record_type, "record_id": x.record_id,
            "batch_id": x.batch_id, "recipient": x.recipient, "phone": x.phone,
            "frequency": x.frequency, "status": x.status, "error": x.error,
            "channel_type": x.channel_type, "operator_name": x.operator_name,
            "created_at": x.created_at.isoformat() if x.created_at else None,
            "content": x.content,
        } for x in items],
        "total": total, "page": page, "page_size": page_size,
    }
