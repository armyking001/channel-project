from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import logging
import traceback
from app.database import get_db
from app.models import User, UserRole, AuditAction
from app.schemas import UserCreate, UserUpdate, UserResponse, UserPasswordReset, MessageResponse
from app.auth import get_current_user, require_admin, require_manager, require_important_or_admin, hash_password
from app.services.audit import write_audit

router = APIRouter(prefix="/api/users", tags=["用户管理"])
log = logging.getLogger("users")


@router.get("", response_model=List[UserResponse])
def list_users(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """用户列表 - 用于审批人选择等场景
    权限：所有已登录用户均可调用（用于项目表单的"选择审批人"）
    - 系统管理员：看全部用户
    - 重要管理员：自己 + 下属 + 自己的上级（向上递归到 admin）
    - 重要账号/普通账号：自己的上级（向上递归到 admin）+ 所有系统管理员
    """
    if current_user.role == UserRole.admin:
        # 系统管理员：全部
        q = db.query(User).order_by(User.id)
        if not include_inactive:
            q = q.filter(User.is_active == True)
        return q.all()
    elif current_user.role == UserRole.archive:
        # 档案管理：可以看到所有用户（只读）
        q = db.query(User).order_by(User.id)
        if not include_inactive:
            q = q.filter(User.is_active == True)
        return q.all()
    else:
        # 重要账号/普通账号：自己的上级链（递归到 admin）+ 所有系统管理员
        ids = set()
        # 向上递归找所有上级
        p = current_user.parent
        while p is not None:
            ids.add(p.id)
            p = p.parent
        # 加上所有系统管理员
        admin_ids = [u.id for u in db.query(User).filter(
            User.role == UserRole.admin,
            User.is_active == True
        ).all()]
        ids.update(admin_ids)
        # 加上自己（可选，便于表单显示）
        ids.add(current_user.id)
        q = db.query(User).filter(User.id.in_(ids)).order_by(User.id)
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
        raise HTTPException(status_code=404, detail='用户不存在')
    changes = {}
    if user_data.username is not None and user_data.username != user.username:
        # 唯一性校验
        existing = db.query(User).filter(User.username == user_data.username, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f'账号 {user_data.username} 已被其他用户占用')
        changes['username'] = {'old': user.username, 'new': user_data.username}
        user.username = user_data.username
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


@router.put("/{user_id}/reject", response_model=MessageResponse)
def reject_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """驳回账号申请：
    - 标记 is_active=False + is_rejected=True（保留记录，可在"已驳回"列表查看）
    - 清理 username 前缀（去掉 !PENDING_），但加 __rej_<ts> 后缀避免冲突
    - 关联数据保留
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if user.is_rejected:
        raise HTTPException(status_code=400, detail='该用户已被驳回')
    import time as _time
    # 清理 PENDING 前缀 + 加 rej 后缀（避免 username 冲突 + 标识驳回）
    base = (user.username or '').replace('!PENDING_', '')
    new_username = f"{base}__rej_{int(_time.time())}"
    old_username = user.username
    user.username = new_username
    user.is_active = False
    user.is_rejected = True
    db.commit()
    db.refresh(user)
    write_audit(
        current_user, AuditAction.user_delete,
        target_type='user', target_id=user.id, target_name=f"{user.real_name}({old_username})",
        details={'reject': True, 'old_username': old_username, 'new_username': new_username},
        request=request,
    )
    return MessageResponse(message=f'已驳回申请 {old_username}')


@router.delete("/{user_id}/hard", response_model=MessageResponse)
def hard_delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """彻底删除用户（仅限已停用/已驳回用户）：
    - 物理删除记录（不可恢复）
    - 关联数据：项目 creator_id/approver_id 用 SET NULL 兜底
    - 通常用于清理"已驳回"占位
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if user.is_active:
        raise HTTPException(status_code=400, detail='只能彻底删除"已停用/已驳回"用户（不能删活跃用户）')
    if user.role == 'admin':
        admin_count = db.query(User).filter(User.role == UserRole.admin, User.is_active == True, User.id != user_id).count()
        if admin_count < 1:
            raise HTTPException(status_code=400, detail='至少需要保留 1 个系统管理员账号')

    real_name = user.real_name
    username = user.username
    # 处理项目中的 FK
    try:
        from app.models import Project
        db.query(Project).filter(Project.created_by == user_id).update({'created_by': None})
        db.query(Project).filter(Project.approver_id == user_id).update({'approver_id': None})
    except Exception:
        pass
    # 处理上下级关系
    try:
        db.query(User).filter(User.parent_id == user_id).update({'parent_id': None})
    except Exception:
        pass
    db.delete(user)
    db.commit()
    try:
        write_audit(
            current_user, AuditAction.user_delete,
            target_type='user', target_id=user_id, target_name=f"{real_name}({username})",
            details={'hard_delete': True}, request=request,
        )
    except Exception:
        pass
    return MessageResponse(message=f'已彻底删除用户 {real_name}({username})')


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
