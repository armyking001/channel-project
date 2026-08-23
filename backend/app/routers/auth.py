from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditAction, UserRole
from app.schemas import UserLogin, TokenResponse, UserResponse, MessageResponse, ApplyAccountResponse
from app.auth import verify_password, create_access_token, get_current_user, hash_password
from app.services.audit import write_audit
from app.services.pinyin_util import generate_username
import secrets
import string

router = APIRouter(prefix="/api/auth", tags=["认证"])

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    """登录接口
    支持账号或姓名登录：
      - 先按 username 精确匹配
      - 找不到时按 real_name 精确匹配（取第一个活跃用户）
    """
    login_id = (form_data.username or '').strip()
    user = db.query(User).filter(User.username == login_id, User.is_active == True).first()
    if not user:
        # 兼容「用姓名登录」
        user = db.query(User).filter(User.real_name == login_id, User.is_active == True).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号/姓名或密码错误")
    token = create_access_token(data={"sub": str(user.id)})
    # 记录登录审计
    if user is not None:
        try:
            write_audit(
                user, AuditAction.user_login,
                target_type='user', target_id=user.id, target_name=f"{user.real_name}({user.username})",
                request=request,
            )
        except Exception:
            pass
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改自己的密码（任何登录用户可用）
    - 必须提供旧密码（验证身份）
    - 新密码和确认密码必须一致
    - 新密码至少 6 位
    """
    # 验证旧密码
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail='旧密码错误')
    # 验证新密码长度
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail='新密码至少 6 位')
    # 验证两次输入一致
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail='两次输入的新密码不一致')
    # 不能与旧密码相同
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail='新密码不能与旧密码相同')
    # 更新密码
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    # 审计
    try:
        write_audit(
            current_user, AuditAction.user_password_change,
            target_type='user', target_id=current_user.id, target_name=f"{current_user.real_name}({current_user.username})",
            request=request,
        )
    except Exception:
        pass
    return MessageResponse(message='密码修改成功，请使用新密码重新登录')

@router.post("/register", response_model=UserResponse)
def register(
    username: str,
    password: str,
    real_name: str,
    role: str = "normal",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可注册账号")
    from app.models import UserRole
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        role=UserRole(role)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class ApplyAccountRequest(BaseModel):
    real_name: str


@router.post("/apply-account", response_model=ApplyAccountResponse)
def apply_account(
    data: ApplyAccountRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """公开接口：申请账号
    - 用户只需提供姓名
    - 后端自动生成 username（名首字母 + 姓全拼），如 szhang、jfli
    - 系统同时生成 8 位随机密码作为初始密码（仅申请成功时返回一次，申请人务必保存）
    - 重复时自动追加 01/02/...
    - 默认 is_active=False（待审批），管理员在「用户管理」处审批通过后立即可用该密码登录
    """
    real_name = (data.real_name or '').strip()
    if not real_name:
        raise HTTPException(400, detail='姓名不能为空')
    if len(real_name) > 50:
        raise HTTPException(400, detail='姓名过长（最多 50 字符）')

    # 检查同姓名是否已经有 pending 用户（避免重复申请）
    # 只找 is_active=False 且 is_rejected=False 的（真正的待审批）
    existing_pending = db.query(User).filter(
        User.real_name == real_name,
        User.is_active == False,
        User.is_rejected == False,
    ).first()
    if existing_pending:
        # 同姓名已有 pending 申请：复用之前的 initial_password
        # 如果数据库里 pending_password 有值（之前会话已存的明文），返回给用户
        # 否则为 None（旧数据）
        return ApplyAccountResponse(
            username=existing_pending.username.replace('!PENDING_', ''),
            real_name=existing_pending.real_name,
            status='pending',
            message=f'您已申请过账号 "{existing_pending.username.replace("!PENDING_", "")}"，请等待管理员审核',
            initial_password=existing_pending.pending_password,  # 返回之前生成的密码
        )

    # 生成基础 username
    base = generate_username(real_name)
    if not base:
        raise HTTPException(400, detail='姓名无效，无法生成账号')

    # 唯一化：如果已存在（无论是否激活），追加 01/02/...
    def exists_fn(name: str) -> bool:
        return db.query(User).filter(User.username == name).first() is not None

    n = 0
    candidate = base
    while exists_fn(candidate):
        n += 1
        candidate = f'{base}{n:02d}'
        if n > 99:
            candidate = f'{base}_{int(__import__("time").time())}'
            break

    # 生成 8 位随机密码：大小写字母 + 数字（不含易混字符）
    alphabet = string.ascii_letters + string.digits
    initial_password = ''.join(secrets.choice(alphabet) for _ in range(8))

    # 创建待审批用户：is_active=False
    # username 加 !PENDING_ 前缀，前端用户管理列表用此识别"待审批"
    # 前端展示时去掉前缀、审批通过后保留真账号名（去掉前缀）
    user = User(
        username='!PENDING_' + candidate,
        # 使用系统生成的 8 位随机密码作为初始密码 hash
        password_hash=hash_password(initial_password),
        pending_password=initial_password,  # 明文存到数据库，供审批时预填
        real_name=real_name,
        role=UserRole.normal,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 审计
    try:
        write_audit(
            user, AuditAction.user_create,
            target_type='user', target_id=user.id, target_name=f"{user.real_name}({user.username})",
            details={'source': 'apply-account', 'status': 'pending'},
            request=request,
        )
    except Exception:
        pass

    # 通知所有系统管理员 — 有新的账号申请待审批
    try:
        from app.services.notifications import send_notification
        from app.models import UserRole, NotificationType
        admins = db.query(User).filter(User.role == UserRole.admin, User.is_active == True).all()
        for admin in admins:
            send_notification(
                db,
                receiver_id=admin.id,
                type=NotificationType.account_apply,
                title="新账号申请待审批",
                content="{0} 申请了账号 \"{1}\"，请尽快审批。".format(real_name, candidate),
                target_type="user", target_id=user.id,
            )
        db.commit()
    except Exception:
        pass

    return ApplyAccountResponse(
        username=candidate,
        real_name=real_name,
        status='pending',
        message=f'账号 "{candidate}" 申请成功，请保存好初始密码并等待系统管理员审核。审核通过后即可用该密码登录。',
        initial_password=initial_password,
    )
