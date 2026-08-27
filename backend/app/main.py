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
from app.routers import auth, users, projects, approvals, reports, file_storage, forms, storage_zones, project_followups, agents, agent_prompts, system as system_router
from app.routers.audit import router as audit_router
from app.routers.notifications_ws import router as notifications_router, ws_router as notifications_ws_router

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
    # 把当前事件循环交给 NotificationManager,便于同步 DB 操作 schedule 异步 WS 推送
    try:
        import asyncio as _asyncio
        from app.services.notifications import set_event_loop
        set_event_loop(_asyncio.get_running_loop())
        print('[startup] NotificationManager 绑定事件循环 OK')
    except Exception as e:
        print(f'[warn] 绑定 NotificationManager 事件循环失败: {e}')
    # 启动时创建所有表
    Base.metadata.create_all(bind=engine)
    # 兼容旧库：手动加 is_rejected 列
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            if 'is_rejected' not in cols:
                c.execute("ALTER TABLE users ADD COLUMN is_rejected INTEGER DEFAULT 0")
                print('[migrate] users.is_rejected 列已添加')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 is_rejected 失败: {e}")
    # 兼容旧库：手动加 pending_password 列
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            if 'pending_password' not in cols:
                c.execute("ALTER TABLE users ADD COLUMN pending_password VARCHAR(50)")
                print('[migrate] users.pending_password 列已添加')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 pending_password 失败: {e}")
    # 兼容旧库：手动加 responsible_sales 列
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()]
            if 'responsible_sales' not in cols:
                c.execute("ALTER TABLE projects ADD COLUMN responsible_sales VARCHAR(100)")
                print('[migrate] projects.responsible_sales 列已添加')
            if 'win_bid_status_set_at' not in cols:
                c.execute("ALTER TABLE projects ADD COLUMN win_bid_status_set_at DATETIME")
                print('[migrate] projects.win_bid_status_set_at 列已添加')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 responsible_sales 失败: {e}")
    # 兼容旧库：project_followups 加 form_data 列
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'project_followups' not in tables:
                # 表会在 Base.metadata.create_all 之后创建；这里只处理已存在的表
                pass
            else:
                cols = [r[1] for r in c.execute("PRAGMA table_info(project_followups)").fetchall()]
                if 'form_data' not in cols:
                    c.execute("ALTER TABLE project_followups ADD COLUMN form_data TEXT")
                    print('[migrate] project_followups.form_data 列已添加')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 project_followups.form_data 失败: {e}")
    # 清理 project_followups.form_data 中的非标准字符串（如 Python str(dict) 而非 JSON）
    try:
        import sqlite3 as _sqlite3
        import json as _json_clean
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'project_followups' in tables:
                cols = [r[1] for r in c.execute("PRAGMA table_info(project_followups)").fetchall()]
                if 'form_data' in cols:
                    rows = c.execute("SELECT id, form_data FROM project_followups WHERE form_data IS NOT NULL AND form_data != ''").fetchall()
                    fixed = 0
                    for rid, fd in rows:
                        if not isinstance(fd, str):
                            continue
                        # 先尝试解析
                        try:
                            _json_clean.loads(fd)
                            continue  # 已经是合法 JSON，跳过
                        except Exception:
                            pass
                        # 不是合法 JSON，安全降级为 NULL（旧数据不兼容）
                        c.execute("UPDATE project_followups SET form_data = NULL WHERE id = ?", (rid,))
                        fixed += 1
                    if fixed:
                        c.commit()
                        print(f'[migrate] project_followups.form_data 已清理 {fixed} 条非标准字符串')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 清理 project_followups.form_data 失败: {e}")
    # 创建 form_templates / form_instances 表（表单生成器）
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'form_templates' not in tables:
                c.execute("""CREATE TABLE form_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    fields TEXT NOT NULL DEFAULT '[]',
                    storage_sub_path VARCHAR(200),
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
                print('[migrate] form_templates 表已创建')
            else:
                cols = [r[1] for r in c.execute("PRAGMA table_info(form_templates)").fetchall()]
                if 'storage_sub_path' not in cols:
                    c.execute("ALTER TABLE form_templates ADD COLUMN storage_sub_path VARCHAR(200)")
                    print('[migrate] form_templates.storage_sub_path 列已添加')
            if 'form_instances' not in tables:
                c.execute("""CREATE TABLE form_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL REFERENCES form_templates(id),
                    data TEXT NOT NULL DEFAULT '{}',
                    tender_folder VARCHAR(500),
                    bid_folder VARCHAR(500),
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
                print('[migrate] form_instances 表已创建')
            else:
                cols = [r[1] for r in c.execute("PRAGMA table_info(form_instances)").fetchall()]
                if 'tender_folder' not in cols:
                    c.execute("ALTER TABLE form_instances ADD COLUMN tender_folder VARCHAR(500)")
                    print('[migrate] form_instances.tender_folder 列已添加')
                if 'bid_folder' not in cols:
                    c.execute("ALTER TABLE form_instances ADD COLUMN bid_folder VARCHAR(500)")
                    print('[migrate] form_instances.bid_folder 列已添加')
            c.commit()
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 创建 form_templates 表失败: {e}")
    # 兼容旧库：把 file_storage_config.template 从 {real_name} 升级到 {responsible_sales}
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            cur = c.execute("UPDATE file_storage_config SET template='{responsible_sales}+{project_name}+{date}' WHERE template='{real_name}+{project_name}+{date}'")
            if cur.rowcount > 0:
                print('[migrate] file_storage_config.template 已从 {real_name} 升级为 {responsible_sales}')
            c.commit()
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 template 失败: {e}")
    # 创建 storage_zones 表（存储区域）
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'storage_zones' not in tables:
                c.execute("""CREATE TABLE storage_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    mode VARCHAR(20) NOT NULL DEFAULT 'webdav',
                    local_path VARCHAR(500),
                    webdav_url VARCHAR(500),
                    webdav_port INTEGER,
                    webdav_use_ssl BOOLEAN DEFAULT 1,
                    webdav_username VARCHAR(100),
                    webdav_password VARCHAR(200),
                    webdav_base_path VARCHAR(500),
                    sub_path VARCHAR(200),
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
                print('[migrate] storage_zones 表已创建')
            # 兼容旧库：projects / form_templates 添加 storage_zone_id
            for table in ('projects', 'form_templates'):
                cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
                if 'storage_zone_id' not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN storage_zone_id INTEGER REFERENCES storage_zones(id)")
                    print(f'[migrate] {table}.storage_zone_id 列已添加')
            # 兼容旧库：projects 添加 source / form_instance_id
            pcols = [r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()]
            if 'source' not in pcols:
                c.execute("ALTER TABLE projects ADD COLUMN source VARCHAR(20) DEFAULT 'channel'")
                print('[migrate] projects.source 列已添加')
            if 'form_instance_id' not in pcols:
                c.execute("ALTER TABLE projects ADD COLUMN form_instance_id INTEGER REFERENCES form_instances(id)")
                print('[migrate] projects.form_instance_id 列已添加')
            # 兼容旧库：form_instances 添加 storage_zone_id / approver_id / approval_status / updated_at
            fcols = [r[1] for r in c.execute("PRAGMA table_info(form_instances)").fetchall()]
            if 'storage_zone_id' not in fcols:
                c.execute("ALTER TABLE form_instances ADD COLUMN storage_zone_id INTEGER REFERENCES storage_zones(id)")
                print('[migrate] form_instances.storage_zone_id 列已添加')
            if 'approver_id' not in fcols:
                c.execute("ALTER TABLE form_instances ADD COLUMN approver_id INTEGER REFERENCES users(id)")
                print('[migrate] form_instances.approver_id 列已添加')
            if 'approval_status' not in fcols:
                c.execute("ALTER TABLE form_instances ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending_submit'")
                print('[migrate] form_instances.approval_status 列已添加')
            if 'updated_at' not in fcols:
                c.execute("ALTER TABLE form_instances ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                print('[migrate] form_instances.updated_at 列已添加')
            c.commit()
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 创建 storage_zones 表失败: {e}")
    # 创建默认管理员
    from app.database import SessionLocal
    from app.models import User, UserRole, FormTemplate, StorageZone
    from app.auth import hash_password
    from app.services.builtin_templates import CHANNEL_PROJECT_TEMPLATE, SELF_PROJECT_TEMPLATE, FOLLOWUP_TEMPLATE
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            # 首次启动时创建默认管理员账号
            # 密码优先从环境变量读取（生产环境必须设置），未设置时使用临时默认值（启动时打印提示）
            import os
            default_pwd = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'Admin@2026')
            env_was_set = 'DEFAULT_ADMIN_PASSWORD' in os.environ
            admin = User(
                username="admin",
                password_hash=hash_password(default_pwd),
                real_name="系统管理员",
                role=UserRole.admin
            )
            db.add(admin)
            db.commit()
            if env_was_set:
                print(f"默认管理员已创建: admin / <DEFAULT_ADMIN_PASSWORD 环境变量值>")
            else:
                print(f"⚠️  默认管理员已创建: admin / Admin@2026")
                print(f"    建议立即登录后修改密码！或通过环境变量 DEFAULT_ADMIN_PASSWORD 预置自定义初始密码。")

        # 同步两个内置表单模板（渠道项目 + 自营项目）
        # 策略：仅在首次（数据库中不存在时）用代码里的字段初始化；已存在的模板不再覆盖
        # 这样用户在 FormBuilder 中编辑的修改会被保留，不会被后端重启抹掉
        try:
            import json
            # 兼容：把旧名「自建项目登记表」迁移为新名「自营项目登记表」
            old_self = db.query(FormTemplate).filter(FormTemplate.name == '自建项目登记表').first()
            new_self = db.query(FormTemplate).filter(FormTemplate.name == '自营项目登记表').first()
            if old_self and not new_self:
                old_self.name = '自营项目登记表'
                db.commit()
                print('[migrate] form_templates: 自建项目登记表 → 自营项目登记表')
            for builtin in [CHANNEL_PROJECT_TEMPLATE, SELF_PROJECT_TEMPLATE, FOLLOWUP_TEMPLATE]:
                fields_json = json.dumps(builtin['fields'], ensure_ascii=False)
                existing = db.query(FormTemplate).filter(FormTemplate.name == builtin['name']).first()
                if existing:
                    # 已存在：只更新元数据（description/storage_zone_id），不覆盖 fields
                    # （fields 由用户在 FormBuilder 中维护，代码不强制覆盖）
                    existing.description = builtin.get('description', '')
                    if builtin.get('storage_zone_id'):
                        existing.storage_zone_id = builtin.get('storage_zone_id')
                    if builtin.get('storage_sub_path'):
                        existing.storage_sub_path = builtin.get('storage_sub_path')
                    existing.is_active = True
                    print(f"[sync] 内置模板已存在,保留用户编辑: {builtin['name']} (id={existing.id})")
                else:
                    tpl = FormTemplate(
                        name=builtin['name'],
                        description=builtin.get('description', ''),
                        fields=fields_json,
                        storage_sub_path=builtin.get('storage_sub_path'),
                        storage_zone_id=builtin.get('storage_zone_id'),
                        is_active=True,
                        created_by=admin.id,
                    )
                    db.add(tpl)
                    print(f"[sync] 内置模板已创建: {builtin['name']}")
            db.commit()
        except Exception as e:
            print(f"[warn] 同步内置模板失败: {e}")

        # 同步默认存储区域（迁移自 file_storage_config）
        try:
            from app.models import FileStorageConfig, StorageMode, FormInstance as _FI, User as _User, UserRole as _UR, ApprovalStatus as _AS
            import json as _json
            default_zone = db.query(StorageZone).filter(StorageZone.name == '默认存储').first()
            if not default_zone:
                # 从 file_storage_config 读取旧配置创建默认区域
                fsc = db.query(FileStorageConfig).first()
                if fsc:
                    default_zone = StorageZone(
                        name='默认存储',
                        mode=fsc.mode or StorageMode.webdav,
                        local_path=fsc.local_path,
                        webdav_url=fsc.webdav_url,
                        webdav_port=fsc.webdav_port,
                        webdav_use_ssl=bool(fsc.webdav_use_ssl) if fsc.webdav_use_ssl is not None else True,
                        webdav_username=fsc.webdav_username,
                        webdav_password=fsc.webdav_password,
                        webdav_base_path=fsc.webdav_base_path,
                        description='系统迁移自旧配置（存储模式/连接信息）',
                        sort_order=0,
                        is_active=True,
                    )
                else:
                    default_zone = StorageZone(
                        name='默认存储',
                        mode=StorageMode.webdav,
                        description='默认 WebDAV 存储区域',
                        is_active=True,
                    )
                db.add(default_zone)
                db.commit()
                print(f'[sync] 创建默认存储区域: {default_zone.name} (id={default_zone.id})')
        except Exception as e:
            print(f"[warn] 同步默认存储区域失败: {e}")

        # 补全历史 FormInstance 缺失字段（tender_folder / bid_folder / approver_id / storage_zone_id）
        try:
            from app.services.form_file_storage import _get_zone, _ensure_form_directories_zone, _ensure_form_directories, _get_cfg
            from app.services.file_storage import render_zone_root, render_subfolder, render_project_root
            from sqlalchemy import func as _func
            instances = db.query(_FI).filter(
                (_func.coalesce(_FI.tender_folder, '') == '') |
                (_FI.approver_id == None)
            ).all()
            fixed = 0
            for inst in instances:
                tpl = db.query(FormTemplate).filter(FormTemplate.id == inst.template_id).first()
                if not tpl:
                    continue
                try:
                    payload = _json.loads(inst.data or '{}')
                except Exception:
                    payload = {}
                project_name = payload.get('project_name') or payload.get('name') or f'表单{inst.id}'
                responsible_sales = payload.get('responsible_sales')

                # 自动分配审批人
                if not inst.approver_id:
                    owner = db.query(_User).filter(_User.id == inst.created_by).first()
                    approver_id = None
                    if owner and owner.parent_id:
                        approver_id = owner.parent_id
                    else:
                        admin = db.query(_User).filter(_User.role == _UR.admin, _User.is_active == True).first()
                        if admin:
                            approver_id = admin.id
                    if approver_id:
                        inst.approver_id = approver_id

                # 解析存储区域
                zone = _get_zone(db, tpl.storage_zone_id)
                if zone and not inst.storage_zone_id:
                    inst.storage_zone_id = zone.id

                # 重建目录路径
                if not inst.tender_folder or not inst.bid_folder:
                    owner = db.query(_User).filter(_User.id == inst.created_by).first()
                    if owner:
                        if zone:
                            root = render_zone_root(zone, owner.username, owner.real_name,
                                                    project_name, responsible_sales or owner.real_name,
                                                    inst.created_at)
                            t_dir = render_subfolder(root, '招标资料')
                            b_dir = render_subfolder(root, '投标文档')
                        else:
                            cfg = _get_cfg(db)
                            root = render_project_root(cfg, owner.username, owner.real_name,
                                                      project_name, responsible_sales or owner.real_name,
                                                      inst.created_at)
                            t_dir = render_subfolder(root, '招标资料')
                            b_dir = render_subfolder(root, '投标文档')
                        inst.tender_folder = t_dir
                        inst.bid_folder = b_dir

                # 更新审批状态
                if not inst.approval_status or inst.approval_status == _AS.pending_submit:
                    inst.approval_status = _AS.pending_approval
                fixed += 1
            if fixed > 0:
                db.commit()
                print(f'[migrate] 已补全 {fixed} 条历史 FormInstance 字段')
        except Exception as e:
            print(f"[warn] 补全历史 FormInstance 失败: {e}")
            import traceback
            traceback.print_exc()
    finally:
        db.close()
    # 兼容旧库：users 加 phone / dingtalk_user_id 列
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            if 'phone' not in cols:
                c.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
                print('[migrate] users.phone 列已添加')
            if 'dingtalk_user_id' not in cols:
                c.execute("ALTER TABLE users ADD COLUMN dingtalk_user_id VARCHAR(100)")
                print('[migrate] users.dingtalk_user_id 列已添加')
            c.commit()
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 迁移 users.phone/dingtalk_user_id 失败: {e}")
    # 创建 notifications / notification_settings / notification_channels 表
    try:
        import sqlite3 as _sqlite3
        from app.database import load_config
        cfg = load_config()
        path = cfg["database"]["url"].replace("sqlite:///", "", 1)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        c = _sqlite3.connect(path, timeout=10)
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receiver_id INTEGER NOT NULL REFERENCES users(id),
                type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                content TEXT,
                target_type VARCHAR(50),
                target_id INTEGER,
                is_read INTEGER NOT NULL DEFAULT 0,
                read_at DATETIME,
                extra TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_notifications_receiver_id ON notifications(receiver_id)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications(type)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read)")
            c.execute("""CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                type VARCHAR(50) NOT NULL,
                in_app INTEGER NOT NULL DEFAULT 1,
                sms INTEGER NOT NULL DEFAULT 0,
                dingtalk INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_notification_settings_user_id ON notification_settings(user_id)")
            c.execute("""CREATE TABLE IF NOT EXISTS notification_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                config TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
            c.commit()
            print('[migrate] notifications 三表已就绪')
        finally:
            c.close()
    except Exception as e:
        print(f"[warn] 创建 notifications 表失败: {e}")
    # 启动时只做一次 connect，结束后 dispose，避免文件句柄长期持有
    engine.dispose()
    yield
    # 关闭时再 dispose 一次
    engine.dispose()

app = FastAPI(
    title="销售项目管理系统V2.1",
    version="2.1.0",
    lifespan=lifespan
)


@app.on_event("startup")
async def _register_event_loop():
    """把当前事件循环交给 NotificationManager,便于在同步 DB 操作中 schedule 异步 WS 推送"""
    from app.services.notifications import set_event_loop
    import asyncio
    set_event_loop(asyncio.get_running_loop())

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
app.include_router(system_router.router)
app.include_router(forms.router)
app.include_router(storage_zones.router)
app.include_router(project_followups.router)
app.include_router(agents.router)
app.include_router(agent_prompts.router)
app.include_router(notifications_router)
app.include_router(notifications_ws_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# 根路径重定向到管理 UI
@app.get("/", include_in_schema=False)
def root_redirect():
    if os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return RedirectResponse(url="/admin/")
    return {"message": "项目管理系统V2.1 API", "docs": "/docs", "admin_ui": "/admin/"}

NO_CACHE_HEADERS = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"}

# 管理 UI：挂在 /admin 路径
if os.path.exists(STATIC_DIR):
    # 静态资源 (assets 等) — 本版本 Starlette StaticFiles 不支持自定义 headers，依赖 no-cache 通过 index.html 路径强制
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
                # JS/CSS 也强制不缓存，确保新版本生效
                return FileResponse(file_path, headers=NO_CACHE_HEADERS)
        # 否则返回 index.html（SPA 路由）— 强制不缓存，确保新版 JS 总能拉到
        return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers=NO_CACHE_HEADERS)

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
