"""
Internal metadata database — async SQLAlchemy session management.

Uses asyncpg driver for non-blocking I/O.

  CRITICAL ASYNC/SYNC SAFETY:
  • All relationships have lazy="raise" to prevent accidental lazy-loads in async context
  • expire_on_commit=False ensures attributes remain accessible after commit
  • ORM objects MUST be converted to Pydantic DTOs inside the session scope
  • Never return raw ORM objects from endpoints—they may lazy-load after session closes
  • Always use selectinload() for relationships accessed in responses
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.max_pool_size,
    max_overflow=5,
    # NullPool is safer for serverless / limited connections during tests
    # poolclass=NullPool,
)

# ── Session factory ───────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # ← CRUCIAL: keeps attributes accessible after commit for ORM→DTO conversion
)


# ── Dependency for FastAPI routes ─────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a DB session and handles commit/rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context manager (for use outside route handlers) ─────────────────────────

@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
