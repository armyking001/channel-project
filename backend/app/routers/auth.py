from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditAction, UserRole
from app.schemas import UserLogin, TokenResponse, UserResponse, MessageResponse
from app.auth import verify_password, create_access_token, get_current_user, hash_password
from app.services.audit import write_audit
from app.services.pinyin_util import generate_username

router = APIRouter(prefix="/api/auth", tags=["认证"])

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username, User.is_active == True).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
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


class ApplyAccountResponse(BaseModel):
    username: str
    real_name: str
    status: str  # "pending"
    message: str


@router.post("/apply-account", response_model=ApplyAccountResponse)
def apply_account(
    data: ApplyAccountRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """公开接口：申请账号
    - 用户只需提供姓名
    - 后端自动生成 username（名首字母 + 姓全拼），如 szhang、jfli
    - 重复时自动追加 01/02/...
    - 默认 is_active=False（待审批），管理员在「用户管理」处确认并分配密码后启用
    """
    real_name = (data.real_name or '').strip()
    if not real_name:
        raise HTTPException(400, detail='姓名不能为空')
    if len(real_name) > 50:
        raise HTTPException(400, detail='姓名过长（最多 50 字符）')

    # 检查同姓名是否已经有 pending 用户（避免重复申请）
    existing_pending = db.query(User).filter(
        User.real_name == real_name,
        User.is_active == False,
    ).first()
    if existing_pending:
        return ApplyAccountResponse(
            username=existing_pending.username,
            real_name=existing_pending.real_name,
            status='pending',
            message=f'您已申请过账号 "{existing_pending.username}"，请等待管理员审核',
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

    # 创建待审批用户：is_active=False
    # username 加 !PENDING_ 前缀，前端用户管理列表用此识别"待审批"
    # 前端展示时去掉前缀、审批通过后保留真账号名（去掉前缀）
    user = User(
        username='!PENDING_' + candidate,
        # 设置一个"无法登录"的临时密码 hash
        password_hash=hash_password('!PENDING_' + candidate),
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

    return ApplyAccountResponse(
        username=candidate,
        real_name=real_name,
        status='pending',
        message=f'账号 "{candidate}" 申请成功，请等待系统管理员审核并设置初始密码',
    )
