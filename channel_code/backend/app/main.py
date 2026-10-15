import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import yaml

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.routers import auth, users, projects, approvals, reports, file_storage
from app.routers.audit import router as audit_router

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
STATIC_DIR = os.path.join(BASE_DIR, "static")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

config = load_config()
app_config = config.get("app", {})
cors_origins = app_config.get("cors_origins", ["http://localhost:5173", "http://127.0.0.1:5173"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 先创建 audit_logs 表（独立管理，避免 SA 干扰）
    try:
        from app.services.audit import ensure_audit_table
        ensure_audit_table()
    except Exception as e:
        print(f"[warn] ensure_audit_table 失败: {e}")
    # 启动时创建所有表
    Base.metadata.create_all(bind=engine)
    # 创建默认管理员
    from app.database import SessionLocal
    from app.models import User, UserRole
    from app.auth import hash_password
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                real_name="系统管理员",
                role=UserRole.admin
            )
            db.add(admin)
            db.commit()
            print("默认管理员已创建: admin / admin123")
    finally:
        db.close()
    # 启动时只做一次 connect，结束后 dispose，避免文件句柄长期持有
    engine.dispose()
    yield
    # 关闭时再 dispose 一次
    engine.dispose()

app = FastAPI(
    title="渠道项目登记与审批管理系统",
    version="1.0.0",
    lifespan=lifespan
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    print(f"[HTTP EXC] {request.method} {request.url.path}: {exc.status_code} {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                        headers=exc.headers if hasattr(exc, 'headers') else None)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"[VALIDATION ERROR] {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    import traceback
    print(f"[UNHANDLED EXC] {request.method} {request.url.path}: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(approvals.router)
app.include_router(reports.router)
app.include_router(file_storage.router)
app.include_router(audit_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# 根路径重定向到管理 UI
@app.get("/", include_in_schema=False)
def root_redirect():
    if os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return RedirectResponse(url="/admin/")
    return {"message": "渠道项目登记与审批管理系统 API", "docs": "/docs", "admin_ui": "/admin/"}

# 管理 UI：挂在 /admin 路径
if os.path.exists(STATIC_DIR):
    # 静态资源 (assets 等)
    app.mount("/admin/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="admin-assets")

    # SPA 路由 fallback —— /admin 与 /admin/* 都返回 index.html
    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/", include_in_schema=False)
    @app.get("/admin/{path:path}", include_in_schema=False)
    def admin_spa(path: str = ""):
        # 先尝试直接返回静态文件（解决 /admin/logo.png 等顶层文件）
        if path:
            file_path = os.path.join(STATIC_DIR, path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
        # 否则返回 index.html（SPA 路由）
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    # 兜底：/login、/projects 等用户误输入的前端 SPA 路径 → 重定向到 /admin/
    # 仅匹配常见前端路径，避免吞掉真正的 404
    SPA_FALLBACK_PATHS = {"login", "projects", "approvals", "reports", "file-storage"}
    for _spa in SPA_FALLBACK_PATHS:
        @app.get(f"/{_spa}", include_in_schema=False)
        @app.get(f"/{_spa}/", include_in_schema=False)
        def _spa_fallback(_name=_spa):
            return RedirectResponse(url=f"/admin/#{_name}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_config.get("host", "0.0.0.0"),
        port=app_config.get("port", 8000),
        reload=app_config.get("debug", True)
    )
