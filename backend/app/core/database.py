"""
Database configuration and session management.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Convert postgresql:// to postgresql+asyncpg:// only if not already async
raw_dsn = str(settings.DATABASE_URL)
DATABASE_URL = (
    raw_dsn
    if raw_dsn.startswith("postgresql+asyncpg://")
    else raw_dsn.replace("postgresql://", "postgresql+asyncpg://")
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database with PostGIS extension."""
    async with engine.begin() as conn:
        # Enable PostGIS extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
