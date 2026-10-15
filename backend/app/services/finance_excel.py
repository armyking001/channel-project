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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    FinanceReceivable, FinanceTrust, FinanceReminderLog,
    NotificationChannel, User,
)

log = logging.getLogger("finance")


# ============ 短信摘要渲染工具 ============
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_]+)(?::([^}]+))?\}")


def _format_value(v: Any, fmt: Optional[str], default: str) -> str:
    """单字段渲染：处理空值、datetime、format-spec（如 :,.2f / :%m-%d）
    日期/时间无格式说明时默认 %Y%m%d 紧凑输出 (节省短信字符)"""
    if v is None or v == "":
        return default
    # 兜底: 日期/时间无格式说明 -> 紧凑 8 位数字
    if fmt is None:
        if hasattr(v, "strftime"):
            try:
                return v.strftime("%Y%m%d")
            except Exception:
                pass
        s = str(v).strip()
        return s or default
    try:
        if hasattr(v, "strftime"):
            return v.strftime(fmt)
        if isinstance(v, (int, float)):
            cleaned = fmt.replace("¥", "").replace("$", "")
            prefix = "¥" if "¥" in fmt else ("$" if "$" in fmt else "")
            return prefix + format(v, cleaned)
        return format(v, fmt)
    except Exception:
        if hasattr(v, "strftime"):
            try:
                return v.strftime("%Y%m%d")
            except Exception:
                pass
        s = str(v).strip()
        return s or default


def render_summary(template: str, record, default_when_missing: str = "-") -> str:
    """把 {field} / {field:fmt} 占位符替换为 record 上的值,缺失字段返回 default_when_missing"""
    def repl(m):
        field = m.group(1)
        fmt = m.group(2)
        v = getattr(record, field, None) if record is not None else None
        return _format_value(v, fmt, default_when_missing)
    return _PLACEHOLDER_RE.sub(repl, template or "")


def trim_to_chars(text: str, max_chars: int) -> str:
    """按字符数裁剪(中文/标点算1字);超出末尾加 … """
    if not text or not max_chars or max_chars <= 0:
        return text or ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _load_sms_custom_cfg(db: Session) -> Dict[str, Any]:
    """从 notification_channels 取 sms_custom 通道配置(enabled=True)"""
    ch = db.query(NotificationChannel).filter(
        NotificationChannel.type == "sms_custom",
        NotificationChannel.enabled == True,
    ).first()
    if not ch or not ch.config:
        return {}
    try:
        return json.loads(ch.config)
    except Exception:
        log.warning("[finance] sms_custom config JSON 解析失败")
        return {}


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
    "remind_end_at":    {"提醒结束时间", "提醒结束日期", "remindendat"},
    "frequency":        {"提醒频率", "frequency"},
    "remark":           {"备注", "remark", "说明"},
}

TRUST_COLS = {
    "subject_name":     {"科目名称", "subjectname", "subject"},
    "balance":          {"期末项目余额", "期末借方余额", "期末贷方余额", "项目余额", "期末余额", "余额", "balance", "amount"},
    "category":         {"分类", "类别", "category", "type"},
    "occurred_at":      {"发生时间", "发生日期", "occurredat", "date"},
    "company":          {"公司", "company"},
    "department":       {"部门", "department", "dept"},
    "employee":         {"员工", "员工姓名", "employee", "name"},
    "phone":            {"联系电话", "电话", "手机", "phone", "tel"},
    "owner":            {"对账负责人", "负责人", "对账人", "owner"},
    "plan_repay_date":  {"计划还款时间", "计划归还时间", "计划还款日期", "计划归还日期", "planrepaydate"},
    "remind_start_at":  {"提醒启动时间", "提醒启动日期", "remindstartat"},
    "remind_end_at":    {"提醒结束时间", "提醒结束日期", "remindendat"},
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
    # Excel 序列日期(数字形态, 如 45992.0)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        n = float(v)
        if 1 < n < 100000:
            return datetime(1899, 12, 30) + timedelta(days=n)
        return None
    s = str(v).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d", "%y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # 字符串形态的 Excel 序列日期
    try:
        n = float(s)
        if 1 < n < 100000:
            return datetime(1899, 12, 30) + timedelta(days=n)
    except Exception:
        pass
    return None


def _parse_phone(v: Any) -> Optional[str]:
    """电话/手机号: 去掉 Excel 数值尾部的 .0, 去掉空格与连字符"""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    s = str(v).strip()
    s = re.sub(r"\.0+$", "", s)
    s = re.sub(r"[\s\-]", "", s)
    return s or None


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
            phone=_parse_phone(mapped.get("phone")),
            plan_date=_parse_date(mapped.get("plan_date")),
            remind_start_at=_parse_date(mapped.get("remind_start_at")),
            remind_end_at=_parse_date(mapped.get("remind_end_at")) if mapped.get("remind_end_at") else None,
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
            phone=_parse_phone(mapped.get("phone")),
            owner=(str(mapped.get("owner")).strip() if mapped.get("owner") else None),
            plan_repay_date=_parse_date(mapped.get("plan_repay_date")),
            remind_start_at=_parse_date(mapped.get("remind_start_at")),
            remind_end_at=_parse_date(mapped.get("remind_end_at")) if mapped.get("remind_end_at") else None,
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


# ============ 通道发送 ============

def _resolve_dingtalk_recipient(db: Session, record_type: str, record):
    """按 姓名/电话 在用户表中找已配置钉钉 userid 的收件人"""
    if record_type == "receivables":
        names = [record.sales_person, record.engineer]
    else:
        names = [record.employee, record.owner]
    names = [str(n).strip() for n in names if n]
    phone = (record.phone or "").strip()

    q = db.query(User).filter(User.is_active == True, User.dingtalk_user_id.isnot(None))
    if phone:
        u = q.filter(User.phone == phone).first()
        if u:
            return u
    for n in names:
        u = q.filter(User.real_name == n).first()
        if u:
            return u
    return None


def _resolve_wechat_recipient(db: Session, record_type: str, record):
    """按 姓名/电话 在用户表中找已配置企业微信 userid / 公众号 openid 的收件人"""
    if record_type == "receivables":
        names = [record.sales_person, record.engineer]
    else:
        names = [record.employee, record.owner]
    names = [str(n).strip() for n in names if n]
    phone = (record.phone or "").strip()

    for filter_col in ("wechat_user_id", "wechat_mp_openid"):
        q = db.query(User).filter(User.is_active == True, getattr(User, filter_col).isnot(None))
        if phone:
            u = q.filter(User.phone == phone).first()
            if u:
                return u
        for n in names:
            u = q.filter(User.real_name == n).first()
            if u:
                return u
    return None


def _send_dingtalk_corp(channel, user, title: str, content: str) -> Dict[str, Any]:
    """钉钉企业应用工作通知 -> 指定用户(user.dingtalk_user_id)"""
    import requests
    try:
        cfg = json.loads(channel.config or "{}")
    except Exception:
        return {"ok": False, "error": "钉钉通道配置 JSON 解析失败"}
    corp_id = cfg.get("corp_id") or cfg.get("corpid")
    agent_id = cfg.get("agent_id")
    app_key = cfg.get("app_key")
    app_secret = cfg.get("app_secret")
    if not (corp_id and agent_id and app_key and app_secret):
        return {"ok": False, "error": "钉钉企业应用配置缺少 corp_id/agent_id/app_key/app_secret"}
    if not user or not user.dingtalk_user_id:
        return {"ok": False, "error": "未找到收件人的钉钉 userid, 请在'用户管理'中为该用户填写"}
    from app.services.notifications import _get_dingtalk_token
    token = _get_dingtalk_token(corp_id, app_key, app_secret)
    if not token:
        return {"ok": False, "error": "获取钉钉 access_token 失败"}
    url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token=" + token
    body = {
        "agent_id": agent_id,
        "userid_list": user.dingtalk_user_id,
        "msg": {"msgtype": "text", "text": {"content": f"[{title}] {content}"}},
    }
    try:
        r = requests.post(url, json=body, timeout=10)
        data = r.json()
    except Exception as e:
        return {"ok": False, "error": f"钉钉请求异常: {e}"}
    if data.get("errcode", 0) != 0:
        return {"ok": False, "error": f"钉钉 errcode={data.get('errcode')} {data.get('errmsg')}"}
    return {"ok": True, "task_id": data.get("task_id")}


# ============ 短信发送 ============

def _build_content(
    db: Session,
    record_type: str,
    record,
    override_template: Optional[str] = None,
) -> Tuple[str, str]:
    """根据 sms_custom.cfg 中的 finance_summary_* 模板渲染短信摘要,自动裁剪到 finance_max_chars

    override_template: 若不为空,则本次发送直接用该模板(覆盖 cfg 中的默认值),
                       同时把该模板写回 cfg 持久化(后续发送与定时任务也用新模板)。

    配置 key(放在 sms_custom 通道的 config JSON 里):
      - finance_summary_receivables : 应收账款摘要模板(占位符 {field} / {field:fmt})
      - finance_summary_trust       : 财务借支摘要模板
      - finance_max_chars           : 最大字符数(默认 70)
      - finance_default_when_missing: 空值占位(默认 "-")
    """
    cfg = _load_sms_custom_cfg(db)
    max_chars = int(cfg.get("finance_max_chars") or 70)
    default_missing = cfg.get("finance_default_when_missing") or "-"

    if record_type == "receivables":
        title = "应收账款催收提醒"
        default_template = (
            "【应收】项目{project_name} 客户{customer} 金额¥{amount:,.2f} 计划{plan_date:%Y%m%d}"
        )
        cfg_key = "finance_summary_receivables"
    else:
        title = "财务借支催收提醒"
        default_template = (
            "【借支】{employee} 科目{subject_name} 余额¥{balance:,.2f} 计划{plan_repay_date:%Y%m%d}"
        )
        cfg_key = "finance_summary_trust"

    if override_template is not None and (override_template or "").strip():
        template = override_template
        # 持久化: 回写 cfg,确保下次/定时任务也用新模板
        try:
            ch = db.query(NotificationChannel).filter(
                NotificationChannel.type == "sms_custom"
            ).first()
            if ch:
                cur = {}
                if ch.config:
                    try:
                        cur = json.loads(ch.config)
                    except Exception:
                        cur = {}
                cur[cfg_key] = template
                ch.config = json.dumps(cur, ensure_ascii=False)
                db.add(ch)
                db.commit()
        except Exception as e:
            log.warning(f"[finance] 回写模板失败: {e}")
    else:
        template = cfg.get(cfg_key) or default_template

    content = render_summary(template, record, default_missing)
    content = trim_to_chars(content, max_chars)
    return title, content


# 默认通道优先级: 短信(sms_custom → aliyun → tencent) > 钉钉企业 > 企业微信 > 公众号
DEFAULT_CHANNEL_ORDER = [
    "sms_custom", "sms_aliyun", "sms_tencent",
    "dingtalk_corp",
    "wechat_corp",
    "wechat_mp",
]


def _try_send_one_channel(db: Session, ctype: str, record_type: str, record, title: str, content: str, phone: str, recipient: str) -> Dict[str, Any]:
    """尝试按指定通道发送; 返回 {ok, status, channel, error?}"""
    ch = db.query(NotificationChannel).filter(
        NotificationChannel.type == ctype, NotificationChannel.enabled == True,
    ).first()
    if not ch:
        return {"ok": False, "channel": ctype, "error": "通道未配置或未启用"}
    if ctype.startswith("sms_"):
        if not phone:
            return {"ok": False, "channel": ctype, "error": "无联系电话"}
        try:
            from app.services.notifications import _send_sms_custom_sync
            if ctype == "sms_custom":
                cfg = json.loads(ch.config or "{}")
                return {**_send_sms_custom_sync(cfg, phone, title, content), "channel": ctype}
            if ctype == "sms_aliyun":
                log.info(f"[finance.sms] aliyun placeholder -> {phone}")
                return {"ok": True, "status_code": 200, "response_text": "aliyun placeholder", "channel": ctype}
            if ctype == "sms_tencent":
                log.info(f"[finance.sms] tencent placeholder -> {phone}")
                return {"ok": True, "status_code": 200, "response_text": "tencent placeholder", "channel": ctype}
        except Exception as e:
            return {"ok": False, "channel": ctype, "error": f"异常: {e}"}
    if ctype == "dingtalk_corp":
        u = _resolve_dingtalk_recipient(db, record_type, record)
        if not u:
            return {"ok": False, "channel": ctype, "error": f"未找到收件人「{recipient or '-'}」的钉钉 userid"}
        return {**_send_dingtalk_corp(ch, u, title, content), "channel": ctype}
    if ctype == "wechat_corp":
        u = _resolve_wechat_recipient(db, record_type, record)
        if not u or not u.wechat_user_id:
            return {"ok": False, "channel": ctype, "error": f"未找到收件人「{recipient or '-'}」的企业微信 userid"}
        from app.services.notifications import _send_wechat_corp_sync
        try:
            cfg = json.loads(ch.config or "{}")
            res = _send_wechat_corp_sync(cfg, u.wechat_user_id, title, content)
            return {**res, "channel": ctype}
        except Exception as e:
            return {"ok": False, "channel": ctype, "error": f"异常: {e}"}
    if ctype == "wechat_mp":
        u = _resolve_wechat_recipient(db, record_type, record)
        if not u or not u.wechat_mp_openid:
            return {"ok": False, "channel": ctype, "error": f"未找到收件人「{recipient or '-'}」的公众号 openid"}
        from app.services.notifications import _send_wechat_mp_template_sync
        try:
            cfg = json.loads(ch.config or "{}")
            res = _send_wechat_mp_template_sync(cfg, u.wechat_mp_openid, title, content)
            return {**res, "channel": ctype}
        except Exception as e:
            return {"ok": False, "channel": ctype, "error": f"异常: {e}"}
    return {"ok": False, "channel": ctype, "error": f"未知通道 {ctype}"}


def send_sms_for_record(db: Session, record_type: str, record, frequency: str, operator,
                        channels: Optional[List[str]] = None,
                        custom_template: Optional[str] = None) -> Dict[str, Any]:
    """对单条记录触发催款.
    channels: 本次允许走的通道顺序(子集), 例如 ['sms_custom','dingtalk_corp','wechat_mp'].
              默认按 DEFAULT_CHANNEL_ORDER 顺序, 命中可用通道即停止, 写一条日志.
    custom_template: 本次发送使用的模板(覆盖 cfg 中的 finance_summary_*);
                     若非空,会同步写回 cfg 持久化。
    返回: {ok, status, channel, error?}
    """
    title, content = _build_content(db, record_type, record, override_template=custom_template)
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

    if not phone and not _resolve_dingtalk_recipient(db, record_type, record) and not _resolve_wechat_recipient(db, record_type, record):
        log_row.status = "skipped"
        log_row.error = "无任何联系方式(手机/钉钉/微信)"
        record.last_status = "skipped"
        db.commit()
        return {"ok": False, "status": "skipped", "error": "无任何联系方式", "channel": None}

    # 提醒结束时间检查: 超过 remind_end_at 不再发送 (即便有频率也停)
    if getattr(record, "remind_end_at", None) is not None:
        if datetime.utcnow() > record.remind_end_at:
            log_row.status = "skipped"
            log_row.error = f"已超过提醒结束时间 {record.remind_end_at.isoformat()}"
            record.last_status = "skipped"
            db.commit()
            return {"ok": False, "status": "skipped", "error": log_row.error, "channel": None}

    order = [c for c in (channels or DEFAULT_CHANNEL_ORDER) if c]
    if not order:
        order = list(DEFAULT_CHANNEL_ORDER)

    last_err = None
    last_channel = None
    for ctype in order:
        res = _try_send_one_channel(db, ctype, record_type, record, title, content, phone, recipient)
        last_channel = ctype
        if res.get("ok"):
            log_row.status = "sent"
            log_row.channel_type = ctype
            log_row.provider_response = json.dumps({k: v for k, v in res.items() if k not in ("channel",)}, ensure_ascii=False)[:1000]
            record.last_status = "sent"
            record.reminder_count = (record.reminder_count or 0) + 1
            record.last_reminder_at = datetime.utcnow()
            db.commit()
            return {"ok": True, "status": "sent", "channel": ctype, "error": None}
        last_err = res.get("error")
    # 全失败
    log_row.status = "failed"
    log_row.channel_type = last_channel
    log_row.error = (last_err or "全部通道失败")[:500]
    log_row.provider_response = json.dumps({"attempted": order}, ensure_ascii=False)[:1000]
    record.last_status = "failed"
    db.commit()
    return {"ok": False, "status": "failed", "channel": last_channel, "error": log_row.error}
