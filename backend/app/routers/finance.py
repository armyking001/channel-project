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
import json
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
from app.models import NotificationChannel

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
    行为:
      - frequency == 'once': 立即调用 send_sms_for_record 走真实通道发送
      - frequency in (daily/weekly/monthly): 只把频率持久化到记录上,
        由 reminder_scheduler 在 remind_start_at 到点时统一调度, 点击瞬间不发
    返回: {success, sent, failed, skipped, no_channel, scheduled, warning?, items: [...]}
    """
    record_type = (payload.get("record_type") or "").strip()
    if record_type not in ("receivables", "trust"):
        raise HTTPException(status_code=400, detail="record_type 必须为 receivables 或 trust")
    person_name = (payload.get("person_name") or "").strip()
    record_ids = payload.get("record_ids") or []
    frequency = (payload.get("frequency") or "once").strip()
    if frequency not in ("once", "daily", "weekly", "monthly"):
        frequency = "once"
    channels = payload.get("channels") or None  # 本次允许的通道顺序
    custom_template = (payload.get("custom_template") or "").strip() or None  # 用户在弹窗编辑的模板

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
        return {
            "success": True, "record_type": record_type, "target_count": 0,
            "sent": 0, "failed": 0, "skipped": 0, "no_channel": 0, "scheduled": 0,
            "items": [],
        }

    sent = failed = skipped = no_channel = scheduled = 0
    warning_msg = None
    items = []

    if frequency == "once":
        # 仅一次: 立即走真实通道发送
        for rec in records:
            try:
                res = send_sms_for_record(
                    db, record_type, rec, frequency, current_user,
                    channels=channels, custom_template=custom_template,
                )
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
                    "next_run_at": None,
                })
            except Exception as e:
                log.exception("send reminder failed for record_id=%s", rec.id)
                failed += 1
                items.append({"record_id": rec.id, "status": "failed", "error": str(e)[:200], "channel": None, "next_run_at": None})
    else:
        # 周期频率: 只把频率写到记录上, 实际发送由 reminder_scheduler 在 remind_start_at 到点时调度
        for rec in records:
            try:
                start_at = getattr(rec, "remind_start_at", None)
                if start_at is None:
                    skipped += 1
                    items.append({
                        "record_id": rec.id,
                        "phone": getattr(rec, "phone", None),
                        "status": "skipped",
                        "error": "未设置提醒启动时间,无法按周期频率排程",
                        "channel": None,
                        "next_run_at": None,
                    })
                    continue
                # 把频率持久化到记录上 (若不同), 让 scheduler 按此频率调度
                if (rec.frequency or "once") != frequency:
                    rec.frequency = frequency
                scheduled += 1
                items.append({
                    "record_id": rec.id,
                    "phone": getattr(rec, "phone", None),
                    "status": "scheduled",
                    "error": None,
                    "channel": None,
                    "next_run_at": start_at.isoformat(),
                })
            except Exception as e:
                log.exception("schedule reminder failed for record_id=%s", rec.id)
                failed += 1
                items.append({"record_id": rec.id, "status": "failed", "error": str(e)[:200], "channel": None, "next_run_at": None})
        try:
            db.commit()
        except Exception as e:
            log.exception("commit scheduled reminder failed")
            db.rollback()

    out = {
        "success": True,
        "record_type": record_type,
        "target_count": len(records),
        "frequency": frequency,
        "sent": sent, "failed": failed, "skipped": skipped, "no_channel": no_channel,
        "scheduled": scheduled,
        "items": items,
    }
    if warning_msg:
        out["warning"] = warning_msg
    return out


# ============ 短信模板(前端编辑框读写) ============

_TEMPLATE_KEYS = {
    "receivables": "finance_summary_receivables",
    "trust": "finance_summary_trust",
}
_TEMPLATE_DEFAULTS = {
    "receivables": "【应收】项目{project_name} 客户{customer} 金额¥{amount:,.2f} 计划{plan_date:%Y%m%d}",
    "trust": "【借支】{employee} 科目{subject_name} 余额¥{balance:,.2f} 计划{plan_repay_date:%Y%m%d}",
}


def _get_sms_custom_cfg(db: Session) -> dict:
    ch = db.query(NotificationChannel).filter(NotificationChannel.type == "sms_custom").first()
    if not ch or not ch.config:
        return {}
    try:
        return json.loads(ch.config)
    except Exception:
        return {}


@router.get("/reminder/template")
def api_get_reminder_template(
    record_type: str = Query(..., regex="^(receivables|trust)$"),
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """读取 sms_custom.cfg 中保存的模板(若未保存则返回硬编码默认)。
    返回: {record_type, template, default_template, fields:[...], max_chars}
    """
    cfg = _get_sms_custom_cfg(db)
    key = _TEMPLATE_KEYS[record_type]
    template = cfg.get(key) or _TEMPLATE_DEFAULTS[record_type]
    # 字段提示:供前端在编辑框下方展示可用的占位符
    if record_type == "receivables":
        fields = [
            {"key": "contract_no",   "label": "合同号"},
            {"key": "project_name",  "label": "项目名称"},
            {"key": "customer",      "label": "客户"},
            {"key": "amount",        "label": "应收款"},
            {"key": "sales_person",  "label": "商务"},
            {"key": "engineer",      "label": "工程人员"},
            {"key": "phone",         "label": "联系电话"},
            {"key": "plan_date",     "label": "计划收款时间", "fmt": "%Y%m%d"},
        ]
    else:
        fields = [
            {"key": "subject_name",     "label": "科目名称"},
            {"key": "balance",          "label": "期末项目余额"},
            {"key": "category",         "label": "分类"},
            {"key": "occurred_at",      "label": "发生时间", "fmt": "%Y%m%d"},
            {"key": "company",          "label": "公司"},
            {"key": "department",       "label": "部门"},
            {"key": "employee",         "label": "员工"},
            {"key": "phone",            "label": "联系电话"},
            {"key": "owner",            "label": "对账负责人"},
            {"key": "plan_repay_date",  "label": "计划还款时间", "fmt": "%Y%m%d"},
        ]
    return {
        "record_type": record_type,
        "template": template,
        "default_template": _TEMPLATE_DEFAULTS[record_type],
        "fields": fields,
        "max_chars": int(cfg.get("finance_max_chars") or 70),
    }


@router.put("/reminder/template")
def api_put_reminder_template(
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
    db: Session = Depends(get_db),
):
    """保存模板到 sms_custom.cfg.config(同时确保 sms_custom 通道存在)。
    payload: {record_type: 'receivables'|'trust', template: '...'}
    """
    record_type = (payload.get("record_type") or "").strip()
    template = (payload.get("template") or "").strip()
    if record_type not in _TEMPLATE_KEYS:
        raise HTTPException(status_code=400, detail="record_type 必须为 receivables 或 trust")
    if not template:
        raise HTTPException(status_code=400, detail="template 不能为空")

    ch = db.query(NotificationChannel).filter(NotificationChannel.type == "sms_custom").first()
    if not ch:
        ch = NotificationChannel(
            type="sms_custom",
            name="短信通道-自定义HTTP",
            enabled=True,
            config="{}",
        )
        db.add(ch)
        db.flush()
    cur = {}
    if ch.config:
        try:
            cur = json.loads(ch.config)
        except Exception:
            cur = {}
    cur[_TEMPLATE_KEYS[record_type]] = template
    ch.config = json.dumps(cur, ensure_ascii=False)
    db.add(ch)
    db.commit()
    return {"success": True, "record_type": record_type, "template": template}


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


# ============ 批量修改提醒字段(启动时间/结束时间/频率) ============

@router.put("/reminder/bulk-update")
def api_bulk_update_reminder(
    payload: dict,
    current_user: User = Depends(require_finance_or_admin),
):
    """批量修改提醒字段
    Body: {
      record_type: "receivables" | "trust",
      record_ids: [int, ...],
      remind_start_at?: "2026-10-15T14:30" | null,   # 缺省=不改; null=清空
      remind_end_at?:   同上,
      frequency?:       "once"|"daily"|"weekly"|"monthly" | null
    }
    返回: { updated, skipped, fields_set, errors: [{id, msg}] }
    """
    rt = (payload.get("record_type") or "").strip().lower()
    if rt not in ("receivables", "trust"):
        raise HTTPException(status_code=400, detail="record_type 必须为 receivables/trust")
    ids = payload.get("record_ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="record_ids 不能为空")
    ids = [int(x) for x in ids if str(x).strip() and str(x).lstrip("-").isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="record_ids 不能为空")

    # 收集要更新的字段(以 payload 中显式出现的键为准,值非空=覆盖,null=清空,缺省=跳过)
    fields_to_set = []  # [(col_name, value_or_None)]
    if "remind_start_at" in payload:
        v = payload["remind_start_at"]
        if v in (None, "", "null"):
            fields_to_set.append(("remind_start_at", None))
        else:
            parsed = _parse_iso_datetime(v)
            if parsed is None:
                raise HTTPException(status_code=400, detail=f"无法解析 remind_start_at: {v!r}")
            fields_to_set.append(("remind_start_at", parsed))
    if "remind_end_at" in payload:
        v = payload["remind_end_at"]
        if v in (None, "", "null"):
            fields_to_set.append(("remind_end_at", None))
        else:
            parsed = _parse_iso_datetime(v)
            if parsed is None:
                raise HTTPException(status_code=400, detail=f"无法解析 remind_end_at: {v!r}")
            fields_to_set.append(("remind_end_at", parsed))
    if "frequency" in payload:
        v = payload["frequency"]
        if v in (None, "", "null"):
            fields_to_set.append(("frequency", None))
        else:
            v = str(v).strip().lower()
            if v not in ("once", "daily", "weekly", "monthly"):
                raise HTTPException(status_code=400, detail="frequency 必须为 once/daily/weekly/monthly")
            fields_to_set.append(("frequency", v))

    if not fields_to_set:
        raise HTTPException(status_code=400, detail="至少要指定一个要更新的字段")

    # 字段白名单 + 表名
    table = "finance_receivables" if rt == "receivables" else "finance_trust"
    allowed = {"remind_start_at", "remind_end_at", "frequency"}
    set_clauses = []
    params = []
    for col, val in fields_to_set:
        if col not in allowed:
            continue
        set_clauses.append(f"{col} = ?")
        params.append(val)  # None -> SQL NULL
    set_sql = ", ".join(set_clauses)

    # 用纯 sqlite3 直连(避开 SA 锁竞争), autocommit + busy_timeout
    from app.database import load_config
    cfg = load_config()
    db_path = cfg["database"]["url"].replace("sqlite:///", "", 1)
    if db_path.startswith("/") and len(db_path) > 2 and db_path[2] == ":":
        db_path = db_path[1:]
    import sqlite3 as _sqlite3
    c = _sqlite3.connect(db_path, timeout=15, isolation_level=None)
    try:
        c.execute("PRAGMA busy_timeout = 15000")
        c.execute("PRAGMA journal_mode = MEMORY")
        # 校验 ID 存在性,过滤掉无效 ID
        placeholders = ",".join(["?"] * len(ids))
        existing_rows = c.execute(
            f"SELECT id FROM {table} WHERE id IN ({placeholders})", ids
        ).fetchall()
        existing_ids = {r[0] for r in existing_rows}
        missing = [i for i in ids if i not in existing_ids]

        updated = 0
        errors = [{"id": mid, "msg": "记录不存在"} for mid in missing]
        for rid in existing_ids:
            try:
                c.execute(
                    f"UPDATE {table} SET {set_sql} WHERE id = ?",
                    params + [rid],
                )
                updated += 1
            except Exception as e:
                errors.append({"id": rid, "msg": str(e)})
        return {
            "success": True,
            "record_type": rt,
            "requested": len(ids),
            "updated": updated,
            "skipped": len(missing),
            "fields_set": [col for col, _ in fields_to_set],
            "errors": errors,
        }
    finally:
        c.close()


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
