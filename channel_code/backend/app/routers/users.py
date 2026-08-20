from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import logging
import traceback
from app.database import get_db
from app.models import User, UserRole, AuditAction
from app.schemas import UserCreate, UserUpdate, UserResponse, UserPasswordReset, MessageResponse
from app.auth import get_current_user, require_admin, require_manager, hash_password
from app.services.audit import write_audit

router = APIRouter(prefix="/api/users", tags=["用户管理"])
log = logging.getLogger("users")


@router.get("", response_model=List[UserResponse])
def list_users(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """用户列表 - 系统管理员看全部，重要管理员只能看自己+下属"""
    if current_user.role == UserRole.admin:
        q = db.query(User).order_by(User.id)
        if not include_inactive:
            q = q.filter(User.is_active == True)
        return q.all()
    else:
        # 重要管理员：自己 + 下属
        child_ids = [c.id for c in current_user.children]
        child_ids.append(current_user.id)
        q = db.query(User).filter(User.id.in_(child_ids)).order_by(User.id)
        if not include_inactive:
            q = q.filter(User.is_active == True)
        return q.all()


@router.post("", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """只有系统管理员可以创建用户"""
    if user_data.role == UserRole.admin and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="不能创建系统管理员账号")

    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        real_name=user_data.real_name,
        role=user_data.role,
        parent_id=user_data.parent_id,
        is_active=user_data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(
        current_user, AuditAction.user_create,
        target_type='user', target_id=user.id, target_name=f"{user.real_name}({user.username})",
        details={'role': user_data.role.value if hasattr(user_data.role, 'value') else str(user_data.role),
                 'parent_id': user_data.parent_id, 'is_active': user_data.is_active},
        request=request,
    )
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """只有系统管理员可以编辑用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    changes = {}
    if user_data.real_name is not None and user_data.real_name != user.real_name:
        changes['real_name'] = {'old': user.real_name, 'new': user_data.real_name}
        user.real_name = user_data.real_name
    if user_data.role is not None:
        new_role_val = user_data.role.value if hasattr(user_data.role, 'value') else str(user_data.role)
        old_role_val = user.role.value if hasattr(user.role, 'value') else str(user.role)
        if new_role_val != old_role_val:
            changes['role'] = {'old': old_role_val, 'new': new_role_val}
        user.role = user_data.role
    if user_data.parent_id is not None and user_data.parent_id != user.parent_id:
        changes['parent_id'] = {'old': user.parent_id, 'new': user_data.parent_id}
        user.parent_id = user_data.parent_id
    if user_data.is_active is not None and user_data.is_active != user.is_active:
        changes['is_active'] = {'old': user.is_active, 'new': user_data.is_active}
        user.is_active = user_data.is_active
    db.commit()
    db.refresh(user)

    if changes:
        write_audit(
            current_user, AuditAction.user_update,
            target_type='user', target_id=user.id, target_name=f"{user.real_name}({user.username})",
            details=changes, request=request,
        )
    return user


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    request: Request,
    # 故意不要 db 依赖，避免 SA 持锁
    current_user: User = Depends(require_admin)
):
    """停用用户：标记 is_active=0，保留所有关联数据。只能系统管理员操作。"""
    log.warning(f"[delete_user] start id={user_id} by_admin={current_user.id}")
    import sqlite3 as _sqlite3
    import time as _time

    def _do_delete():
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]

        for attempt in range(10):
            c = _sqlite3.connect(path, timeout=60, check_same_thread=False, isolation_level=None)
            try:
                c.execute("PRAGMA busy_timeout=60000")
                c.execute("PRAGMA journal_mode=MEMORY")

                row = c.execute("SELECT id, username, real_name, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="用户不存在")
                target_id, target_username, target_real_name, target_role, target_active = row

                if target_id == current_user.id:
                    raise HTTPException(status_code=400, detail="不能停用自己")

                if target_role == 'admin':
                    admin_count = c.execute(
                        "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1 AND id != ?",
                        (target_id,),
                    ).fetchone()[0]
                    if admin_count < 1:
                        raise HTTPException(status_code=400, detail="至少需要保留 1 个系统管理员账号")

                new_username = f"{target_username}__del_{int(_time.time())}"
                cur = c.execute(
                    "UPDATE users SET is_active = 0, username = ? WHERE id = ?",
                    (new_username, target_id),
                )
                log.warning(f"[delete_user] ok soft-delete id={target_id} username={target_username} -> {new_username} attempt={attempt}")
                return cur.rowcount, target_id, target_real_name, target_username
            except _sqlite3.OperationalError as e:
                err_msg = str(e)
                if "locked" in err_msg or "I/O" in err_msg or "database is locked" in err_msg:
                    log.warning(f"[delete_user] retry attempt={attempt} err={e}")
                    _time.sleep(1.0)
                    continue
                raise
            except HTTPException:
                raise
            except Exception as e:
                log.error(f"[delete_user] error: {e}\n{traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"停用失败: {e}")
            finally:
                try:
                    c.close()
                except Exception:
                    pass
        raise HTTPException(status_code=503, detail="数据库暂时不可用，请重试")

    try:
        result, target_id, target_real_name, target_username = _do_delete()
        write_audit(
            current_user, AuditAction.user_delete,
            target_type='user', target_id=target_id, target_name=f"{target_real_name}({target_username})",
            details={'soft_delete': True}, request=request,
        )
        return MessageResponse(message="用户已停用（关联数据已保留）")
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[delete_user] outer error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"停用失败: {e}")


@router.put("/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(
    user_id: int,
    data: UserPasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """只有系统管理员可以重置密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    write_audit(
        current_user, AuditAction.user_reset_password,
        target_type='user', target_id=user.id, target_name=f"{user.real_name}({user.username})",
        request=request,
    )
    return MessageResponse(message="密码已重置")
