from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
import yaml
import os
import logging
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

logging.basicConfig(
    level=logging.WARNING,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s',
    stream=open(os.path.join(BASE_DIR, "app_debug.log"), "a", encoding="utf-8"),
)
log = logging.getLogger("db")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
db_url = config.get("database", {}).get("url", "sqlite:///./data.db")
log.warning(f"[db init] url={db_url}")

if db_url.startswith("sqlite"):
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA foreign_keys=ON")
            # 项目自带的 `C:\channel-data` 等路径下，SQLite 写事务时
            # 创建 `data.db-journal` 副文件会失败，抛 CANTOPEN。
            # 改用内存 journal 绕开。某些情况下（如文件被独占）仍可能失败，
            # 用 try 兼容掉，退回默认 delete 模式。
            try:
                cur.execute("PRAGMA journal_mode=MEMORY")
            except Exception:
                pass
        finally:
            cur.close()
else:
    engine = create_engine(db_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        log.error("[get_db] error:\n" + traceback.format_exc())
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
