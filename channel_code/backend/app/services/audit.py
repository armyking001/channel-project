"""审计日志写入助手 - 使用直接 sqlite3 避免 ORM 锁"""
import json
import logging
import sqlite3
import time
from typing import Optional, Any
from app.models import AuditAction, User, UserRole
from fastapi import Request

log = logging.getLogger("audit")

ROLE_LABELS = {
    'admin': '系统管理员',
    'important_admin': '重要管理员',
    'important': '重要账号',
    'normal': '普通账号',
}


def _resolve_db_path() -> str:
    from app.database import load_config
    cfg = load_config()
    raw = cfg["database"]["url"].replace("sqlite:///", "", 1)
    if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
        raw = raw[1:]
    return raw


def ensure_audit_table():
    """确保 audit_logs 表存在。启动时调用。"""
    path = _resolve_db_path()
    c = sqlite3.connect(path, timeout=10)
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username VARCHAR(50) NOT NULL,
                real_name VARCHAR(100),
                role VARCHAR(20),
                action VARCHAR(50) NOT NULL,
                target_type VARCHAR(50),
                target_id INTEGER,
                target_name VARCHAR(200),
                details TEXT,
                ip_address VARCHAR(45),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)")
        c.commit()
    finally:
        c.close()


def write_audit(
    user: User,
    action: AuditAction,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> bool:
    """写入一条审计日志。
    - user: 操作者
    - action: AuditAction
    - target_type/target_id/target_name: 操作对象
    - details: 字典（序列化为 JSON）
    - request: FastAPI Request（用于 IP 记录）
    """
    ip = None
    if request is not None:
        try:
            ip = request.client.host if request.client else None
            # 兼容反向代理
            xff = request.headers.get("x-forwarded-for")
            if xff:
                ip = xff.split(",")[0].strip()
        except Exception:
            pass

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    details_str = json.dumps(details, ensure_ascii=False) if details else None

    path = _resolve_db_path()
    for attempt in range(3):
        c = sqlite3.connect(path, timeout=10, check_same_thread=False, isolation_level=None)
        try:
            c.execute("PRAGMA busy_timeout=10000")
            c.execute("PRAGMA journal_mode=MEMORY")
            c.execute(
                """INSERT INTO audit_logs
                   (user_id, username, real_name, role, action, target_type, target_id, target_name, details, ip_address)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user.id,
                    user.username,
                    user.real_name,
                    role_val,
                    action.value,
                    target_type,
                    target_id,
                    target_name,
                    details_str,
                    ip,
                ),
            )
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "I/O" in str(e):
                time.sleep(0.3)
                continue
            log.warning(f"[audit] write failed: {e}")
            return False
        except Exception as e:
            log.warning(f"[audit] write error: {e}")
            return False
        finally:
            try:
                c.close()
            except Exception:
                pass
    return False
