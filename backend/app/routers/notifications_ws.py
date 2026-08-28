"""通知中心路由 - REST + WebSocket"""
import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.orm import Session

from app.auth import decode_token, get_current_user, require_admin
from app.database import get_db, SessionLocal
from app.models import (
    AuditAction,
    Notification,
    NotificationChannel,
    NotificationGlobalConfig,
    NotificationSetting,
    NotificationTemplate,
    NotificationType,
    User,
)
from app.schemas import (
    MessageResponse,
    NotificationChannelConfig,
    NotificationChannelResponse,
    NotificationGlobalConfigResponse,
    NotificationGlobalConfigUpdate,
    NotificationListResponse,
    NotificationSettingResponse,
    NotificationSettingUpdate,
    NotificationTemplateConfig,
    NotificationTemplateResponse,
    NotificationUnreadResponse,
    SystemAnnouncementRequest,
)
from app.services.audit import write_audit
from app.services.notifications import (
    broadcast_announcement,
    get_effective_setting,
    get_global_config,
    manager as ws_manager,
)

log = logging.getLogger("notifications.api")

router = APIRouter(prefix="/api/notifications", tags=["通知中心"])
ws_router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    only_unread: bool = Query(False),
    type: Optional[NotificationType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.receiver_id == current_user.id)
    if only_unread:
        q = q.filter(Notification.is_read == False)
    if type:
        q = q.filter(Notification.type == type)
    total = q.count()
    unread = db.query(Notification).filter(
        Notification.receiver_id == current_user.id,
        Notification.is_read == False,
    ).count()
    items = q.order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return NotificationListResponse(items=items, total=total, unread_count=unread)


@router.get("/unread", response_model=NotificationUnreadResponse)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.receiver_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return NotificationUnreadResponse(unread_count=n)


@router.post("/{notification_id}/read", response_model=MessageResponse)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.receiver_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在或无权访问")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.commit()
    return MessageResponse(message="已标记为已读")


@router.post("/read-all", response_model=MessageResponse)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(Notification).filter(
        Notification.receiver_id == current_user.id,
        Notification.is_read == False,
    ).all()
    now = datetime.utcnow()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()
    return MessageResponse(message="已标记 {} 条为已读".format(len(rows)))


@router.get("/settings", response_model=List[NotificationSettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    out = []
    for t in NotificationType:
        s = get_effective_setting(db, current_user.id, t)
        out.append(NotificationSettingResponse(
            type=t, in_app=s["in_app"], sms=s["sms"], dingtalk=s["dingtalk"],
        ))
    return out


@router.put("/settings/{ntype}", response_model=NotificationSettingResponse)
def upsert_setting(
    ntype: NotificationType,
    payload: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id,
        NotificationSetting.type == ntype,
    ).first()
    if not row:
        row = NotificationSetting(user_id=current_user.id, type=ntype)
        db.add(row)
    if payload.in_app is not None:
        row.in_app = payload.in_app
    if payload.sms is not None:
        row.sms = payload.sms
    if payload.dingtalk is not None:
        row.dingtalk = payload.dingtalk
    db.commit()
    return NotificationSettingResponse(
        type=ntype, in_app=row.in_app, sms=row.sms, dingtalk=row.dingtalk,
    )


@router.post("/announce", response_model=MessageResponse)
def announce(
    payload: SystemAnnouncementRequest,
    request=None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not payload.title.strip() or not payload.content.strip():
        raise HTTPException(status_code=400, detail="标题和内容不能为空")
    sent = broadcast_announcement(
        db, title=payload.title.strip(),
        content=payload.content.strip(),
        actor_id=current_user.id,
    )
    db.commit()
    try:
        write_audit(current_user, AuditAction.user_update,
                    target_type='announcement', target_id=None, target_name=payload.title,
                    details={'sent': sent}, request=request)
    except Exception:
        pass
    return MessageResponse(message="已群发给 {} 位用户".format(sent))


@router.get("/channels", response_model=List[NotificationChannelResponse])
def list_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return db.query(NotificationChannel).order_by(NotificationChannel.id).all()


@router.post("/channels/{ctype}", response_model=NotificationChannelResponse)
def upsert_channel(
    ctype: str,
    payload: NotificationChannelConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if ctype not in ("dingtalk_webhook", "dingtalk_corp", "sms_aliyun", "sms_tencent", "sms_custom"):
        raise HTTPException(status_code=400, detail="未知通道配置")
    # sms_custom：必须包含 endpoint 和 body_template
    if ctype == "sms_custom":
        if not isinstance(payload.config, dict):
            raise HTTPException(status_code=400, detail="config 必须是 JSON 对象")
        if not payload.config.get("endpoint"):
            raise HTTPException(status_code=400, detail="config.endpoint 必填(短信云平台接收 POST 的 URL)")
        if not payload.config.get("body_template"):
            raise HTTPException(status_code=400, detail="config.body_template 必填(请求体模板, 支持 {phone}/{title}/{content}/{sign_name} 占位符)")
    row = db.query(NotificationChannel).filter(NotificationChannel.type == ctype).first()
    if not row:
        row = NotificationChannel(type=ctype)
        db.add(row)
    row.name = payload.name
    row.config = json.dumps(payload.config, ensure_ascii=False)
    row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return row


@router.post("/channels/{ctype}/test")
def test_channel(
    ctype: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """测试通道 — 当前仅对 sms_custom 真正 POST 一次
    入参: { phone, title?, content? }
    返回: { ok, status_code, response_text, latency_ms, error? }
    """
    import time as _t
    from app.services.notifications import _send_sms_custom_sync
    if ctype != "sms_custom":
        raise HTTPException(status_code=400, detail="该接口目前仅用于 sms_custom 测试")
    phone = (payload or {}).get("phone") or ""
    title = (payload or {}).get("title") or "测试通知"
    content = (payload or {}).get("content") or "这是一条来自销售项目管理系统的测试短信。"
    if not phone:
        raise HTTPException(status_code=400, detail="phone 必填")
    row = db.query(NotificationChannel).filter(
        NotificationChannel.type == ctype,
    ).first()
    if not row or not row.enabled:
        raise HTTPException(status_code=400, detail="sms_custom 通道未配置或未启用")
    try:
        cfg = json.loads(row.config)
    except Exception as e:
        raise HTTPException(status_code=400, detail="config 解析失败: {}".format(e))
    t0 = _t.time()
    try:
        result = _send_sms_custom_sync(cfg, phone, title, content)
        result['latency_ms'] = int((_t.time() - t0) * 1000)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": int((_t.time() - t0) * 1000)}


# ============== 通知文案模板(自定义编辑) ==============
@router.get("/templates", response_model=List[NotificationTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rows = db.query(NotificationTemplate).order_by(
        NotificationTemplate.type, NotificationTemplate.channel,
    ).all()
    return rows


@router.put("/templates/{ntype}/{channel}", response_model=NotificationTemplateResponse)
def upsert_template(
    ntype: str,
    channel: str,
    payload: NotificationTemplateConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if channel not in ("in_app", "dingtalk", "sms"):
        raise HTTPException(status_code=400, detail="通道必须为 in_app / dingtalk / sms")
    valid_types = {t.value for t in NotificationType}
    if ntype not in valid_types:
        raise HTTPException(status_code=400, detail="未知事件类型")
    row = db.query(NotificationTemplate).filter(
        NotificationTemplate.type == ntype,
        NotificationTemplate.channel == channel,
    ).first()
    if not row:
        row = NotificationTemplate(type=ntype, channel=channel)
        db.add(row)
    row.title_template = payload.title_template
    row.content_template = payload.content_template
    row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return row


@router.delete("/templates/{ntype}/{channel}", response_model=MessageResponse)
def delete_template(
    ntype: str,
    channel: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    row = db.query(NotificationTemplate).filter(
        NotificationTemplate.type == ntype,
        NotificationTemplate.channel == channel,
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return MessageResponse(message="已删除模板")


# ============== 全局通知配置(统一题头) ==============
@router.get("/global-config", response_model=NotificationGlobalConfigResponse)
def get_global_cfg(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    row = get_global_config(db)
    return NotificationGlobalConfigResponse(
        title_prefix=row.title_prefix,
        apply_in_app=row.apply_in_app,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.put("/global-config", response_model=NotificationGlobalConfigResponse)
def update_global_cfg(
    payload: NotificationGlobalConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    row = get_global_config(db)
    if payload.title_prefix is not None:
        row.title_prefix = (payload.title_prefix or '').strip() or '【销售项目管理系统V2.1通知】'
    if payload.apply_in_app is not None:
        row.apply_in_app = payload.apply_in_app
    db.commit()
    db.refresh(row)
    return NotificationGlobalConfigResponse(
        title_prefix=row.title_prefix,
        apply_in_app=row.apply_in_app,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@ws_router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception as e:
        log.warning("[ws] auth failed: {}".format(e))
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        await ws_manager.connect(user_id, websocket)
        try:
            unread = db.query(Notification).filter(
                Notification.receiver_id == user_id,
                Notification.is_read == False,
            ).count()
            await websocket.send_text(json.dumps({"event": "notification.unread", "data": {"unread_count": unread}}, ensure_ascii=False))
        except Exception:
            pass
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() in ("ping", '{"event":"ping"}'):
                try:
                    await websocket.send_text(json.dumps({"event": "pong"}, ensure_ascii=False))
                except Exception:
                    break
    except Exception as e:
        log.info("[ws] connection closed: {}".format(e))
    finally:
        await ws_manager.disconnect(user_id, websocket)
        try:
            db.close()
        except Exception:
            pass
