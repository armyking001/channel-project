from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
import yaml
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
jwt_settings = config.get("jwt", {})
# 强制从配置文件读取 secret_key（不提供默认值，避免硬编码）
SECRET_KEY = jwt_settings.get("secret_key")
if not SECRET_KEY:
    raise RuntimeError(
        '配置文件中缺少 jwt.secret_key！\n'
        '请在 backend/config.yaml 中设置：\n'
        '  jwt:\n'
        '    secret_key: "<your-random-secret-key>"'
    )
ALGORITHM = jwt_settings.get("algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = jwt_settings.get("expire_minutes", 1440)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效或已过期")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token无效")
    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在或已冻结")
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要系统管理员权限")
    return current_user

def require_important_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """可以审批：管理员 / 重要管理员 / 重要账号"""
    if current_user.role not in [UserRole.admin, UserRole.important_admin, UserRole.important]:
        raise HTTPException(status_code=403, detail="需要重要账号或管理员权限")
    return current_user

def require_manager(current_user: User = Depends(get_current_user)) -> User:
    """管理员或重要管理员（可查看下属、审批、但不能修改用户）"""
    if current_user.role not in [UserRole.admin, UserRole.important_admin]:
        raise HTTPException(status_code=403, detail="需要管理员或重要管理员权限")
    return current_user
