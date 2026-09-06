from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AuditAction
from app.schemas import UserLogin, TokenResponse, UserResponse, MessageResponse
from app.auth import verify_password, create_access_token, get_current_user, hash_password
from app.services.audit import write_audit

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
