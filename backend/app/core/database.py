"""
数据库引擎与会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings


def _is_sqlite_url(database_url: str) -> bool:
    """判断数据库连接串是否为 SQLite"""
    return database_url.startswith("sqlite")


connect_args = {"check_same_thread": False} if _is_sqlite_url(settings.DATABASE_URL) else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not _is_sqlite_url(settings.DATABASE_URL),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """提供数据库会话的依赖生成器，使用完自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
