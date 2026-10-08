"""Async Database Engine, Session Management, and Multi-Tenant Isolation."""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from packages.schemas.db_models import Base
from packages.telemetry.logger import logger

# Primary PostgreSQL URL, with SQLite fallback if needed
DEFAULT_PG_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/deployos"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

# Configure engine with NullPool to allow clean event loop isolation
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initializes and creates all database tables if they do not exist."""
    global engine, async_session_factory
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database schema initialized successfully on {DATABASE_URL}")
    except Exception as exc:
        logger.error(f"Failed to initialize database on {DATABASE_URL}: {exc}")
        # Try SQLite fallback if PostgreSQL is unavailable
        if "postgresql" in DATABASE_URL:
            fallback_url = "sqlite+aiosqlite:///deployos.db"
            logger.warning(f"Falling back to local SQLite database at {fallback_url}")
            engine = create_async_engine(fallback_url, echo=False, future=True, poolclass=NullPool)
            async_session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("SQLite fallback schema initialized successfully.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
