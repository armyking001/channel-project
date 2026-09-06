"""系统管理：仅 admin 可重启后端服务"""
import asyncio
import os
from fastapi import APIRouter, Depends
from app.database import get_db
from app.models import User, UserRole
from app.auth import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/system", tags=["系统管理"])


@router.post("/restart", response_model=dict)
def restart_service(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """重启后端服务（仅 admin）。返回 200 后会异步执行 systemctl restart。"""
    if current_user.role != UserRole.admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅系统管理员可重启服务")
    # 异步执行重启
    async def _do_restart():
        await asyncio.sleep(0.5)
        try:
            import subprocess
            subprocess.Popen(['sudo', 'systemctl', 'restart', 'channel-project'])
        except Exception as e:
            print(f"[restart] failed: {e}")
    asyncio.create_task(_do_restart())
    return {"message": "服务重启命令已发出，5-10 秒后恢复"}


@router.get("/health", response_model=dict)
def health():
    """健康检查"""
    return {"status": "ok"}