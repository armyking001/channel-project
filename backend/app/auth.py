from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
import yaml
import os
import base64
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
jwt_settings = config.get("jwt", {})
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

BCRYPT_MAX_BYTES = 72

def _normalize_password_bytes(password: str) -> bytes:
    """将任意长度密码归一化为 <= 72 bytes 的安全字节串供 bcrypt 使用
    - UTF-8 编码后 <=72 bytes → 直接使用（保留原有哈希兼容性）
    - 超过 → SHA-256 后用 base64 编码（44 bytes，<72）
    """
    if not isinstance(password, str):
        password = str(password)
    raw = password.encode("utf-8")
    if len(raw) <= BCRYPT_MAX_BYTES:
        return raw
    digest = hashlib.sha256(raw).digest()
    return base64.b64encode(digest)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_normalize_password_bytes(plain), hashed.encode("utf-8"))
    except Exception:
        return False

def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_normalize_password_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")

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
    """可以审批：管理员 / 重要账号"""
    if current_user.role not in [UserRole.admin, UserRole.important]:
        raise HTTPException(status_code=403, detail="需要重要账号或管理员权限")
    return current_user

def require_manager(current_user: User = Depends(get_current_user)) -> User:
    """管理员（可查看审计日志）"""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user

def require_not_archive(current_user: User = Depends(get_current_user)) -> User:
    """档案管理账号不能进行任何写操作"""
    if current_user.role == UserRole.archive:
        raise HTTPException(status_code=403, detail="档案管理账号为只读权限，无法执行此操作")
    return current_user
