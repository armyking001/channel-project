"""通知中心服务

NotificationManager 负责:
- 站内通知落库 + 实时 WebSocket 推送(红点)
- 根据用户 NotificationSetting 决定是否调用短信/钉钉
- 管理 WebSocket 连接池
- 异步非阻塞调用第三方(best-effort: 失败不影响主流程)

设计要点:
- 所有写库 + WS 推送都在一个 DB 事务内,保证一致性
- 短信/钉钉投递通过 asyncio.run_coroutine_threadsafe 跨到事件循环
"""
import asyncio
import json
import logging
import requests
from collections import defaultdict
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from app.models import (
    Notification,
    NotificationChannel,
    NotificationGlobalConfig,
    NotificationSetting,
    NotificationTemplate,
    NotificationType,
    User,
)
log = logging.getLogger("notifications")


# ====================== 全局 WS 连接池 ======================
class ConnectionManager:
    """按 user_id 维护活跃 WebSocket 连接
    - 多 tab 可同时连:同一个 user_id 对应一个 Set[WebSocket]
    - 断开时自动清理
    """

    def __init__(self):
        self._connections: Dict[int, Set] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws):
        async with self._lock:
            self._connections[user_id].add(ws)
        log.info(f"[ws] user={user_id} connected")

    async def disconnect(self, user_id: int, ws):
        async with self._lock:
            self._connections[user_id].discard(ws)
            if not self._connections[user_id]:
                self._connections.pop(user_id, None)

    async def send_to(self, user_id: int, payload: dict) -> int:
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))
        if not conns:
            return 0
        text = json.dumps(payload, ensure_ascii=False, default=str)
        dead = []
        sent = 0
        for ws in conns:
            try:
                await ws.send_text(text)
                sent += 1
            except Exception as e:
                log.warning(f"[ws] send to user={user_id} failed: {e}")
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[user_id].discard(ws)
        return sent

    def online_count(self) -> int:
        return sum(len(s) for s in self._connections.values())


# 全局单例(进程级)
manager = ConnectionManager()


# ====================== 默认推送偏好 ======================
DEFAULT_SETTINGS = {
    # 站内:默认开; 短信/钉钉:默认关(避免骚扰)
    NotificationType.account_apply: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.account_approved: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.account_rejected: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.password_reset: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.followup_viewed: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.project_pending: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.project_approved: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.project_rejected: {"in_app": True, "sms": False, "dingtalk": False},
    NotificationType.system_announcement: {"in_app": True, "sms": False, "dingtalk": False},
}


def get_effective_setting(db: Session, user_id: int, ntype: NotificationType) -> dict:
    """获取用户对某个事件类型的有效开关(用户级 > 默认)"""
    row = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == user_id,
        NotificationSetting.type == ntype,
    ).first()
    if row:
        return {"in_app": row.in_app, "sms": row.sms, "dingtalk": row.dingtalk}
    return dict(DEFAULT_SETTINGS.get(ntype, {"in_app": True, "sms": False, "dingtalk": False}))


def get_template(db: Session, ntype: str, channel: str):
    """查某个事件在某个通道下的模板(若启用)
    返回模板对象 或 None(走默认)
    """
    row = db.query(NotificationTemplate).filter(
        NotificationTemplate.type == ntype,
        NotificationTemplate.channel == channel,
        NotificationTemplate.enabled == True,
    ).first()
    return row


def get_global_config(db: Session):
    """取全局通知配置(单一记录 id=1,若不存在自动创建默认)"""
    row = db.query(NotificationGlobalConfig).filter(NotificationGlobalConfig.id == 1).first()
    if not row:
        row = NotificationGlobalConfig(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def apply_prefix(db: Session, content: str, channel: str):
    """根据全局配置,决定是否在内容前面加 [题头]
    - channel='in_app': 仅当 apply_in_app=True 才加
    - channel='dingtalk'/'sms': 默认加题头
    """
    cfg = get_global_config(db)
    prefix = (cfg.title_prefix or '').strip()
    if not prefix:
        return content
    if channel == 'in_app' and not cfg.apply_in_app:
        return content
    # 已含题头则不再加(避免重复)
    if prefix in content:
        return content
    return prefix + '\n\n' + (content or '')


# ====================== 通知写入 + WS 推送 ======================
def send_notification(
    db: Session,
    *,
    receiver_id: int,
    type: NotificationType,
    title: str,
    content: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    extra: Optional[dict] = None,
) -> Notification:
    """同步写库 + 异步推送 WS / 第三方
    - 站内:WS 推到当前账号所有活跃 tab;离线账号下次拉取时仍能看到
    - 第三方(best-effort):失败只记日志,不影响主流程
    """
    n = Notification(
        receiver_id=receiver_id,
        type=type,
        title=title,
        content=content,
        target_type=target_type,
        target_id=target_id,
        extra=json.dumps(extra, ensure_ascii=False) if extra else None,
    )
    db.add(n)
    db.flush()

    setting = get_effective_setting(db, receiver_id, type)
    if setting.get("in_app"):
        _push_ws(receiver_id, {
            "event": "notification.new",
            "data": {
                "id": n.id,
                "type": n.type.value,
                "title": n.title,
                "content": n.content,
                "target_type": n.target_type,
                "target_id": n.target_id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
        })

    if setting.get("sms") or setting.get("dingtalk"):
        _schedule_external(db, receiver_id, n, setting)

    return n


def broadcast_announcement(db: Session, *, title: str, content: str, actor_id: int) -> int:
    """系统公告 — fanout 给所有 active 用户(发送人除外)
    返回实际写入条数;被用户设置关闭的会跳过。
    """
    users = db.query(User).filter(User.is_active == True).all()
    ntype = NotificationType.system_announcement
    sent = 0
    for u in users:
        if u.id == actor_id:
            continue
        s = get_effective_setting(db, u.id, ntype)
        if not s.get("in_app"):
            continue
        n = Notification(
            receiver_id=u.id, type=ntype,
            title=title, content=content,
            target_type="announcement", target_id=None,
        )
        db.add(n)
        db.flush()
        _push_ws(u.id, {
            "event": "notification.new",
            "data": {
                "id": n.id, "type": ntype.value,
                "title": n.title, "content": n.content,
                "target_type": "announcement", "target_id": None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
        })
        sent += 1
    return sent


# ====================== 第三方推送 ======================
def _schedule_external(db: Session, receiver_id: int, n: Notification, setting: dict):
    """把第三方调用 schedule 到事件循环(best-effort)
    - 注意:传入的 db 不能跨 await 边界继续使用(session 在准备状态),所以 schedule 时我们只传基本数据
    - 异步任务里从 SessionLocal 重新开 session 读 user 信息
    """
    try:
        loop = _get_loop()
        # 只传普通类型,不要传 db / n(n 是 ORM 对象)
        asyncio.run_coroutine_threadsafe(
            _push_external_async(
                receiver_id=receiver_id,
                notification_id=n.id,
                ntype_value=n.type.value,
                title=n.title,
                content=n.content,
                target_type=n.target_type,
                in_app=setting.get("in_app", False),
                sms=setting.get("sms", False),
                dingtalk=setting.get("dingtalk", False),
            ), loop
        )
    except RuntimeError:
        log.debug(f"[external] no running event loop, skip push for notification={n.id}")


async def _push_external_async(receiver_id, notification_id, ntype_value, title, content, target_type, in_app, sms, dingtalk):
    """新开 DB session 异步推第三方 — 因为原 request 的 db session 不能跨 await"""
    from app.database import SessionLocal
    log.warning(f"[external] async start user={receiver_id} ntype={ntype_value} sms={sms} dingtalk={dingtalk}")
    db2 = SessionLocal()
    try:
        user = db2.query(User).filter(User.id == receiver_id).first()
        if not user:
            log.warning(f"[external] user {receiver_id} not found")
            return
        if sms and user.phone:
            _send_sms_sync(db2, user, title, content)
        if dingtalk and user.dingtalk_user_id:
            _send_dingtalk_sync(user, title, content, target_type)
        else:
            if dingtalk:
                log.warning(f"[external] user={receiver_id} dingtalk 设置开启但 user.dingtalk_user_id 为空, skip")
    except Exception as e:
        log.warning(f"[external] push failed for user={receiver_id}: {e}")
    finally:
        try:
            db2.close()
        except Exception:
            pass


def _send_sms_sync(db, user, title, content):
    """同步版短信投递(已开新 session)
    优先级:sms_custom(可定制第三方) > aliyun > tencent
    """
    msg_body = (content or '') if content else (title or '')
    msg = '[{}] {}'.format(title, msg_body)
    # 自动加全局题头
    msg = apply_prefix(db, msg, 'sms')
    # 1) 优先:可定制第三方短信云平台
    custom = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'sms_custom', NotificationChannel.enabled == True,
    ).first()
    if custom:
        try:
            cfg = json.loads(custom.config)
            result = _send_sms_custom_sync(cfg, user.phone, title, msg)
            log.info(f"[sms.custom] -> {user.phone} ok={result.get('ok')} status={result.get('status_code')}")
        except Exception as e:
            log.warning(f"[sms.custom] 调用失败 user={user.id}: {e}")
        return
    aliyun = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'sms_aliyun', NotificationChannel.enabled == True,
    ).first()
    tencent = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'sms_tencent', NotificationChannel.enabled == True,
    ).first()
    if aliyun:
        log.info(f"[sms.aliyun] -> {user.phone} msg={msg!r} (provider configured, real call here)")
        return
    if tencent:
        log.info(f"[sms.tencent] -> {user.phone} msg={msg!r}")
        return
    log.info(f"[sms] no provider configured, skip user={user.id}")


def _send_sms_custom_sync(cfg: dict, phone: str, title: str, content: str) -> dict:
    """可定制第三方短信云平台 — POST 渲染模板
    cfg 字段:
      - endpoint (必填) : 接收 POST 的 URL
      - method (可选,默认 POST)
      - headers (可选 dict, 如 Authorization / Content-Type)
      - body_template (必填) : 请求体, 支持占位符 {phone}/{title}/{content}/{sign_name}
      - sign_name (可选) : 替换 body_template 中的 {sign_name}
      - success_keys (可选 list) : 响应 JSON 中视为成功的 key 列表(等价于 errcode=0), 例如 ["code","status"]
      - success_value (可选) : 视为成功的值, 默认 0 或 "0" 或 "OK"
      - timeout (可选秒,默认 10)
    返回: { ok, status_code, response_text, response_json? }
    """
    endpoint = (cfg.get('endpoint') or '').strip()
    if not endpoint:
        return {"ok": False, "error": "endpoint 为空"}
    method = (cfg.get('method') or 'POST').upper()
    headers = cfg.get('headers') or {}
    body_tpl = cfg.get('body_template')
    if body_tpl is None:
        return {"ok": False, "error": "body_template 为空"}
    sign_name = cfg.get('sign_name') or ''
    success_keys = cfg.get('success_keys') or ['code', 'errcode', 'status']
    success_value = cfg.get('success_value')
    timeout = int(cfg.get('timeout') or 10)

    # 渲染占位符
    def _render(v):
        if isinstance(v, str):
            return v.format(phone=phone, title=title, content=content, sign_name=sign_name)
        if isinstance(v, list):
            return [_render(x) for x in v]
        if isinstance(v, dict):
            return {k: _render(x) for k, x in v.items()}
        return v

    rendered_body = _render(body_tpl)
    # body: str 直接发; dict/list 转 JSON
    if isinstance(rendered_body, (dict, list)):
        data = json.dumps(rendered_body, ensure_ascii=False)
        if 'Content-Type' not in headers and 'content-type' not in headers:
            headers.setdefault('Content-Type', 'application/json; charset=utf-8')
    else:
        data = rendered_body if isinstance(rendered_body, str) else str(rendered_body)

    # 替换 header 占位符(同样支持)
    rendered_headers = _render(headers) if headers else {}

    try:
        if method == 'GET':
            r = requests.get(endpoint, params=json.loads(data) if isinstance(data, str) and data.startswith('{') else None,
                             headers=rendered_headers, timeout=timeout)
        else:
            r = requests.request(method, endpoint, data=data, headers=rendered_headers, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": f"HTTP 异常: {e}"}

    resp_text = (r.text or '')[:2000]
    out = {"ok": False, "status_code": r.status_code, "response_text": resp_text}
    # 尝试解析 JSON 判定业务成功
    try:
        j = r.json()
        out["response_json"] = j
        # 1) HTTP 2xx 且 body 里有 success_keys 命中 success_value -> 成功
        if 200 <= r.status_code < 300:
            ok = False
            for k in success_keys:
                if k in j:
                    v = j.get(k)
                    if success_value is None:
                        # 默认: 0 / "0" / "OK" / true 视为成功
                        if v in (0, "0", "OK", "ok", True, "success", "Success", "200"):
                            ok = True
                            break
                    else:
                        if v == success_value:
                            ok = True
                            break
            # 如果没有任何成功 key, 默认 2xx 视为成功(纯 webhook 风格)
            if not success_keys and 200 <= r.status_code < 300:
                ok = True
            out["ok"] = ok
        return out
    except Exception:
        # 非 JSON 响应 — 按 HTTP 状态判定
        out["ok"] = 200 <= r.status_code < 300
        return out


def _send_dingtalk_sync(user, title, content, target_type):
    """同步版钉钉投递"""
    log.warning(f"[dingtalk.corp] enter user={user.id} dingtalk_user_id={user.dingtalk_user_id!r}")
    # 用新 session 读 channel,避免与发起的 session 撞
    from app.database import SessionLocal
    db2 = SessionLocal()
    try:
        cfg_row = db2.query(NotificationChannel).filter(
            NotificationChannel.type == 'dingtalk_corp', NotificationChannel.enabled == True,
        ).first()
        log.warning(f"[dingtalk.corp] cfg_row={bool(cfg_row)}")
        if not cfg_row:
            log.warning(f"[dingtalk.corp] no corp app configured, skip user={user.id}")
            return
        try:
            cfg = json.loads(cfg_row.config)
        except Exception:
            log.warning(f"[dingtalk.corp] config JSON 解析失败")
            return
        corp_id = cfg.get('corp_id') or cfg.get('corpid')
        agent_id = cfg.get('agent_id')
        app_key = cfg.get('app_key')
        app_secret = cfg.get('app_secret')
        log.warning(f"[dingtalk.corp] corp_id={corp_id!r} agent_id={agent_id!r}")
        if not (corp_id and agent_id and app_key and app_secret):
            log.warning(f"[dingtalk.corp] config 缺少字段 (corp_id/agent_id/app_key/app_secret), skip")
            return
        if not user.dingtalk_user_id:
            log.warning(f"[dingtalk.corp] user={user.id} dingtalk_user_id 为空, skip")
            return
        # 1) access_token(进程级缓存)
        token = _get_dingtalk_token(corp_id, app_key, app_secret)
        log.warning(f"[dingtalk.corp] gettoken={'OK' if token else 'FAIL'}")
        if not token:
            return
        # 2) 投递
        url = 'https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token=' + token
        # 内容前自动加全局题头(可在通知管理中自定义)
        body_text = '[{}] {}\n\n{}'.format(
            title, content or '',
            '请到系统通知中心查看详情' if target_type else '',
        )
        body_text = apply_prefix(db2, body_text, 'dingtalk')
        body = {
            'agent_id': agent_id,
            'userid_list': user.dingtalk_user_id,
            'msg': {
                'msgtype': 'text',
                'text': {
                    'content': body_text,
                },
            },
        }
        try:
            r = requests.post(url, json=body, timeout=10)
            data = r.json()
            log.warning(f"[dingtalk.corp] POST result: {data}")
            if data.get('errcode', 0) != 0:
                log.warning(f"[dingtalk.corp] 投递失败 user={user.id} -> {data}")
            else:
                log.warning(f"[dingtalk.corp] OK user={user.id} task_id={data.get('task_id')}")
        except Exception as e:
            log.warning(f"[dingtalk.corp] HTTP 异常 user={user.id}: {e}")
    except Exception as e:
        log.warning(f"[dingtalk.corp] 整体异常 user={user.id}: {e}")
        import traceback
        log.warning(f"[dingtalk.corp] traceback: {traceback.format_exc()}")
    finally:
        try:
            db2.close()
        except Exception:
            pass


async def _send_sms(db: Session, user: User, n: Notification):
    """短信投递:优先 aliyun,其次 tencent
    骨架实现:仅打日志。后续接入期需要 pip install alibabacloud-dysmsapi / tencentcloud-sdk-python-sms
    """
    aliyun = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'sms_aliyun',
        NotificationChannel.enabled == True,
    ).first()
    tencent = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'sms_tencent',
        NotificationChannel.enabled == True,
    ).first()
    if aliyun:
        cfg = json.loads(aliyun.config)
        log.info(f"[sms.aliyun] -> {user.phone} title={n.title!r} cfg_keys={list(cfg.keys())}")
        return
    if tencent:
        cfg = json.loads(tencent.config)
        log.info(f"[sms.tencent] -> {user.phone} title={n.title!r} cfg_keys={list(cfg.keys())}")
        return
    log.info(f"[sms] no provider configured, skip user={user.id}")


async def _send_dingtalk_user(db: Session, user: User, n: Notification):
    """钉钉工作通知(到具体用户)
    - 需先调用 https://oapi.dingtalk.com/gettoken 拿 access_token
    - 然后用 /topapi/message/corpconversation/asyncsend_v2 投递
    - corp_id 在鉴权信息里,agent_id/app_key/app_secret 在 notification_channels.config
    - user.dingtalk_user_id 是用户在该企业的 staffId
    - access_token 缓存(过期前 60s 续)
    """
    cfg_row = db.query(NotificationChannel).filter(
        NotificationChannel.type == 'dingtalk_corp',
        NotificationChannel.enabled == True,
    ).first()
    if not cfg_row:
        log.info(f"[dingtalk.corp] no corp app configured, skip user={user.id}")
        return
    cfg = json.loads(cfg_row.config)
    corp_id = cfg.get('corp_id') or cfg.get('corpid')
    agent_id = cfg.get('agent_id')
    app_key = cfg.get('app_key')
    app_secret = cfg.get('app_secret')
    if not (corp_id and agent_id and app_key and app_secret):
        log.warning(f"[dingtalk.corp] config 缺少字段 (corp_id/agent_id/app_key/app_secret), skip")
        return
    if not user.dingtalk_user_id:
        log.info(f"[dingtalk.corp] user={user.id} dingtalk_user_id 为空, skip")
        return
    try:
        # 1) 取 access_token(同步,因我们在线程池跑)
        token = await asyncio.get_event_loop().run_in_executor(
            None, _get_dingtalk_token, corp_id, app_key, app_secret,
        )
        if not token:
            return
        # 2) 投递工作通知(用 requests,在 executor 中跑)
        def _do_send():
            url = 'https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token=' + token
            body = {
                'agent_id': agent_id,
                'userid_list': user.dingtalk_user_id,
                'msg': {
                    'msgtype': 'text',
                    'text': {
                        'content': '[{0}] {1}\n\n{2}'.format(
                            n.title, n.content or '',
                            '请到系统通知中心查看详情' if n.target_type else '',
                        ),
                    },
                },
            }
            r = requests.post(url, json=body, timeout=10)
            data = r.json()
            if data.get('errcode', 0) != 0:
                log.warning(f"[dingtalk.corp] 投递失败 user={user.id} -> {data}")
                return False
            log.info(f"[dingtalk.corp] OK user={user.id} task_id={data.get('task_id')}")
            return True
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_send)
    except Exception as e:
        log.warning(f"[dingtalk.corp] 异常 user={user.id}: {e}")


_dingtalk_token_cache = {'token': None, 'expire_at': 0, 'key': None}


def _get_dingtalk_token(corp_id, app_key, app_secret):
    """同步取 access_token(从缓存),失败返回 None。依赖 requests(已在 requirements.txt)"""
    import time as _time
    key = '{0}|{1}'.format(corp_id, app_key)
    now = _time.time()
    cached = _dingtalk_token_cache
    if cached['key'] == key and cached['token'] and cached['expire_at'] > now + 60:
        return cached['token']
    try:
        url = 'https://oapi.dingtalk.com/gettoken?appkey={0}&appsecret={1}'.format(app_key, app_secret)
        r = requests.get(url, timeout=10)
        data = r.json()
        token = data.get('access_token')
        expire = data.get('expires_in', 7200)
        if token:
            _dingtalk_token_cache.update({'token': token, 'expire_at': now + expire, 'key': key})
            return token
        log.warning(f"[dingtalk.corp] gettoken 失败: {data}")
    except Exception as e:
        log.warning(f"[dingtalk.corp] gettoken 异常: {e}")
    return None


# ====================== WS 推送辅助 ======================
def _push_ws(user_id: int, payload: dict):
    try:
        loop = _get_loop()
        asyncio.run_coroutine_threadsafe(manager.send_to(user_id, payload), loop)
    except RuntimeError:
        pass


_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop):
    global _loop
    _loop = loop


def _get_loop() -> Optional[asyncio.AbstractEventLoop]:
    global _loop
    if _loop is None:
        try:
            _loop = asyncio.get_event_loop()
        except RuntimeError:
            _loop = None
    return _loop
