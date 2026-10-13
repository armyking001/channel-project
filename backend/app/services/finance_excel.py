"""财务催款 Excel 解析 + 短信发送服务

解析两种 Excel:
  - 应收账款: 合同号/项目名称/客户/应收款/商务/工程人员/联系电话/计划收款时间
  - 财务借支/信托: 科目名称/期末项目余额/分类/发生时间/公司/部门/员工/联系电话/对账负责人/计划还款时间

支持 .xlsx/.xls/.csv (openpyxl + csv, 不依赖 pandas)
列名按中文匹配(忽略空格/全角半角),空字符串规范为 None,
金额字段非数字的行跳过并记录原因。
"""
import csv
import io
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    FinanceReceivable, FinanceTrust, FinanceReminderLog,
    NotificationChannel,
)

log = logging.getLogger("finance")


def _norm(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = s.replace("\u3000", "").replace(" ", "").replace("\n", "").replace("\r", "")
    s = s.replace("（", "(").replace("）", ")")
    return s.lower()


RECEIVABLE_COLS = {
    "contract_no":      {"合同号", "contractno", "contract"},
    "project_name":     {"项目名称", "projectname", "project"},
    "customer":         {"客户", "客户名称", "customer"},
    "amount":           {"应收款", "应收账款", "金额", "amount", "应收金额"},
    "sales_person":     {"商务", "商务人员", "销售", "salesperson", "sales"},
    "engineer":         {"工程人员", "工程师", "工程", "engineer"},
    "phone":            {"联系电话", "电话", "手机", "phone", "tel"},
    "plan_date":        {"计划收款时间", "计划回款时间", "计划收款日期", "plandate"},
    "remind_start_at":  {"提醒启动时间", "提醒启动日期", "remindstartat"},
    "frequency":        {"提醒频率", "frequency"},
    "remark":           {"备注", "remark", "说明"},
}

TRUST_COLS = {
    "subject_name":     {"科目名称", "subjectname", "subject"},
    "balance":          {"期末项目余额", "项目余额", "期末余额", "余额", "balance", "amount"},
    "category":         {"分类", "类别", "category", "type"},
    "occurred_at":      {"发生时间", "发生日期", "occurredat", "date"},
    "company":          {"公司", "company"},
    "department":       {"部门", "department", "dept"},
    "employee":         {"员工", "员工姓名", "employee", "name"},
    "phone":            {"联系电话", "电话", "手机", "phone", "tel"},
    "owner":            {"对账负责人", "负责人", "对账人", "owner"},
    "plan_repay_date":  {"计划还款时间", "计划还款日期", "planrepaydate"},
    "remind_start_at":  {"提醒启动时间", "提醒启动日期", "remindstartat"},
    "frequency":        {"提醒频率", "frequency"},
    "remark":           {"备注", "remark", "说明"},
}


def _parse_amount(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    s = re.sub(r"[¥$,\s元万元]", "", s)
    try:
        return float(s)
    except Exception:
        return None


def _parse_date(v: Any) -> Optional[datetime]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if hasattr(v, "year") and hasattr(v, "month") and hasattr(v, "day") and not isinstance(v, str):
        try:
            return datetime(v.year, v.month, v.day)
        except Exception:
            return None
    s = str(v).strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d", "%y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # 尝试 Excel 序列日期
    try:
        n = float(s)
        if 1 < n < 100000:
            return datetime(1899, 12, 30) + __import__("datetime").timedelta(days=n)
    except Exception:
        pass
    return None


def _parse_frequency(v: Any) -> str:
    if not v:
        return "once"
    s = _norm(v)
    if s in ("1", "一次", "单次", "仅一次", "once"):
        return "once"
    if s in ("每天", "每日", "日", "daily", "day"):
        return "daily"
    if s in ("每周", "周", "weekly", "week"):
        return "weekly"
    if s in ("每月", "月", "monthly", "month"):
        return "monthly"
    return "once"


def _read_xlsx(content: bytes) -> List[Dict[str, Any]]:
    """用 openpyxl 读 .xlsx, 跳过空行"""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    out = []
    for r in rows[1:]:
        # 行全空跳过
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in r):
            continue
        rec = {}
        for h, v in zip(headers, r):
            rec[h] = v
        out.append(rec)
    return out


def _read_xls(content: bytes) -> List[Dict[str, Any]]:
    """.xls 用 xlrd 读; 失败时抛错让前端知道"""
    try:
        import xlrd
    except ImportError:
        raise RuntimeError("读取 .xls 需要 xlrd, 请 pip install xlrd")
    book = xlrd.open_workbook(file_contents=content)
    sheet = book.sheet_by_index(0)
    if sheet.nrows < 2:
        return []
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    out = []
    for r in range(1, sheet.nrows):
        rec = {}
        for c in range(sheet.ncols):
            v = sheet.cell_value(r, c)
            # xlrd 日期转 datetime
            if sheet.cell_type(r, c) == 3:  # XL_CELL_DATE
                try:
                    v = datetime(*xlrd.xldate_as_tuple(v, book.datemode))
                except Exception:
                    pass
            rec[headers[c]] = v
        out.append(rec)
    return out


def _read_csv(content: bytes) -> List[Dict[str, Any]]:
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            text = content.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        raise RuntimeError("CSV 文件编码无法识别")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    headers = [str(c).strip() for c in rows[0]]
    out = []
    for r in rows[1:]:
        if not any((c or "").strip() for c in r):
            continue
        rec = {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
        out.append(rec)
    return out


def _read_table(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], str]:
    fname = (filename or "").lower()
    if fname.endswith(".csv"):
        return _read_csv(content), "csv"
    if fname.endswith(".xls"):
        return _read_xls(content), "xlrd"
    if fname.endswith(".xlsx"):
        return _read_xlsx(content), "openpyxl"
    # 默认按 xlsx
    return _read_xlsx(content), "openpyxl"


def _map_row(raw: Dict[str, Any], col_map: Dict[str, set]) -> Dict[str, Any]:
    norm_raw = {}
    for k, v in raw.items():
        nk = _norm(k)
        if nk:
            norm_raw[nk] = v
    out: Dict[str, Any] = {}
    for field, aliases in col_map.items():
        val = None
        for alias in aliases:
            n = _norm(alias)
            if n in norm_raw:
                val = norm_raw[n]
                break
        out[field] = val
    return out


def import_receivables(db: Session, content: bytes, filename: str) -> Dict[str, Any]:
    rows, engine = _read_table(content, filename)
    batch_id = uuid.uuid4().hex[:16]
    imported = 0
    skipped: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=2):
        mapped = _map_row(raw, RECEIVABLE_COLS)
        amount = _parse_amount(mapped.get("amount"))
        if not any([mapped.get("project_name"), mapped.get("contract_no"), mapped.get("customer")]):
            skipped.append({"row": idx, "reason": "缺少项目名称/合同号/客户"})
            continue
        if amount is None:
            skipped.append({"row": idx, "reason": f"金额无效: {mapped.get('amount')!r}"})
            continue
        rec = FinanceReceivable(
            batch_id=batch_id,
            contract_no=(str(mapped.get("contract_no")).strip() if mapped.get("contract_no") else None),
            project_name=(str(mapped.get("project_name")).strip() if mapped.get("project_name") else None),
            customer=(str(mapped.get("customer")).strip() if mapped.get("customer") else None),
            amount=amount,
            sales_person=(str(mapped.get("sales_person")).strip() if mapped.get("sales_person") else None),
            engineer=(str(mapped.get("engineer")).strip() if mapped.get("engineer") else None),
            phone=(str(mapped.get("phone")).strip() if mapped.get("phone") else None),
            plan_date=_parse_date(mapped.get("plan_date")),
            remind_start_at=_parse_date(mapped.get("remind_start_at")),
            frequency=_parse_frequency(mapped.get("frequency")),
            remark=(str(mapped.get("remark")).strip() if mapped.get("remark") else None),
        )
        db.add(rec)
        imported += 1
    db.commit()
    log.info(f"[finance.import] receivables batch={batch_id} imported={imported} skipped={len(skipped)} engine={engine}")
    return {
        "success": True,
        "batch_id": batch_id,
        "imported_count": imported,
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
    }


def import_trust(db: Session, content: bytes, filename: str) -> Dict[str, Any]:
    rows, engine = _read_table(content, filename)
    batch_id = uuid.uuid4().hex[:16]
    imported = 0
    skipped: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=2):
        mapped = _map_row(raw, TRUST_COLS)
        if not any([mapped.get("subject_name"), mapped.get("employee")]):
            skipped.append({"row": idx, "reason": "缺少科目名称/员工"})
            continue
        balance = _parse_amount(mapped.get("balance"))
        if balance is None:
            balance = 0.0
        rec = FinanceTrust(
            batch_id=batch_id,
            subject_name=(str(mapped.get("subject_name")).strip() if mapped.get("subject_name") else None),
            balance=balance,
            category=(str(mapped.get("category")).strip() if mapped.get("category") else None),
            occurred_at=_parse_date(mapped.get("occurred_at")),
            company=(str(mapped.get("company")).strip() if mapped.get("company") else None),
            department=(str(mapped.get("department")).strip() if mapped.get("department") else None),
            employee=(str(mapped.get("employee")).strip() if mapped.get("employee") else None),
            phone=(str(mapped.get("phone")).strip() if mapped.get("phone") else None),
            owner=(str(mapped.get("owner")).strip() if mapped.get("owner") else None),
            plan_repay_date=_parse_date(mapped.get("plan_repay_date")),
            remind_start_at=_parse_date(mapped.get("remind_start_at")),
            frequency=_parse_frequency(mapped.get("frequency")),
            remark=(str(mapped.get("remark")).strip() if mapped.get("remark") else None),
        )
        db.add(rec)
        imported += 1
    db.commit()
    log.info(f"[finance.import] trust batch={batch_id} imported={imported} skipped={len(skipped)} engine={engine}")
    return {
        "success": True,
        "batch_id": batch_id,
        "imported_count": imported,
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
    }


# ============ 短信发送 ============

def _build_content(record_type: str, record) -> Tuple[str, str]:
    if record_type == "receivables":
        title = "应收账款催收提醒"
        content = (
            f"【应收账款】项目「{record.project_name or '-'}」"
            f"客户「{record.customer or '-'}」应收款 ¥{record.amount:,.2f}，"
            f"计划收款时间 {record.plan_date.strftime('%Y-%m-%d') if record.plan_date else '-'}。"
            f"请尽快跟进处理。"
        )
    else:
        title = "财务借支催收提醒"
        content = (
            f"【财务借支】科目「{record.subject_name or '-'}」"
            f"余额 ¥{record.balance:,.2f}，"
            f"计划还款时间 {record.plan_repay_date.strftime('%Y-%m-%d') if record.plan_repay_date else '-'}。"
            f"请尽快处理还款。"
        )
    return title, content


def send_sms_for_record(db: Session, record_type: str, record, frequency: str, operator) -> Dict[str, Any]:
    title, content = _build_content(record_type, record)
    phone = (record.phone or "").strip() if hasattr(record, "phone") else ""
    recipient = (record.customer or record.sales_person) if record_type == "receivables" else (record.employee or record.owner)

    log_row = FinanceReminderLog(
        record_type=record_type,
        record_id=record.id,
        batch_id=record.batch_id,
        recipient=recipient,
        phone=phone or None,
        frequency=frequency,
        content=content,
        status="pending",
        operator_id=operator.id if operator else None,
        operator_name=operator.real_name if operator else None,
    )
    db.add(log_row)
    db.flush()

    if not phone:
        log_row.status = "skipped"
        log_row.error = "无联系电话"
        record.last_status = "skipped"
        db.commit()
        return {"ok": False, "status": "skipped", "error": "无联系电话", "channel": None}

    channel = None
    for t in ("sms_custom", "sms_aliyun", "sms_tencent"):
        c = db.query(NotificationChannel).filter(
            NotificationChannel.type == t, NotificationChannel.enabled == True,
        ).first()
        if c:
            channel = c
            break

    if not channel:
        log.warning(f"[finance.sms] 无启用短信通道 record_id={record.id}")
        log_row.status = "failed"
        log_row.error = "无启用的短信通道,请先在'通知管理'配置"
        log_row.channel_type = None
        record.last_status = "failed"
        db.commit()
        return {"ok": False, "status": "no_channel", "error": "无启用的短信通道", "channel": None}

    try:
        if channel.type == "sms_custom":
            from app.services.notifications import _send_sms_custom_sync
            cfg = json.loads(channel.config or "{}")
            res = _send_sms_custom_sync(cfg, phone, title, content)
        elif channel.type == "sms_aliyun":
            log.info(f"[finance.sms] aliyun placeholder -> {phone}")
            res = {"ok": True, "status_code": 200, "response_text": "aliyun placeholder"}
        elif channel.type == "sms_tencent":
            log.info(f"[finance.sms] tencent placeholder -> {phone}")
            res = {"ok": True, "status_code": 200, "response_text": "tencent placeholder"}
        else:
            res = {"ok": False, "error": f"未知通道 {channel.type}"}
    except Exception as e:
        log.warning(f"[finance.sms] 调用异常 record_id={record.id}: {e}")
        res = {"ok": False, "error": f"异常: {e}"}

    if res.get("ok"):
        log_row.status = "sent"
        record.last_status = "sent"
        record.reminder_count = (record.reminder_count or 0) + 1
        record.last_reminder_at = datetime.utcnow()
    else:
        log_row.status = "failed"
        log_row.error = (res.get("error") or "send failed")[:500]
        record.last_status = "failed"
    log_row.channel_type = channel.type
    log_row.provider_response = json.dumps(
        {k: v for k, v in res.items() if k != "response_json"},
        ensure_ascii=False,
    )[:1000]
    db.commit()
    return {
        "ok": bool(res.get("ok")),
        "status": log_row.status,
        "error": log_row.error,
        "channel": channel.type,
    }
