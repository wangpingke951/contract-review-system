"""
app/core/database.py — SQLAlchemy async 引擎 + Session 工厂

关键设计：
- 使用 aiomysql 作为 MySQL 异步驱动
- charset=utf8mb4 强制中文安全
- 通过 Depends(get_db) 在路由里注入，请求结束自动 close
- models/__init__.py 只导出 Base.metadata，不聚合导入 model 文件
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


# ——— Declarative Base ———
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# ——— 异步引擎（单例，模块加载时创建）———
engine: AsyncEngine = create_async_engine(
    settings.mysql_dsn,
    echo=settings.DEBUG,          # DEBUG 模式打印 SQL
    pool_pre_ping=True,           # 连接池中连接失效时自动重连
    pool_size=10,
    max_overflow=20,
)

# ——— 会话工厂 ———
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,        # commit 后可继续访问已加载的对象
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency：在路由中注入 AsyncSession
    使用方式：async def some_route(db: AsyncSession = Depends(get_db)): ...
    请求结束后自动 close session
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
