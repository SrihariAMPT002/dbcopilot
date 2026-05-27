"""
Database initializer — creates all metadata tables on first startup.
Called from the FastAPI lifespan handler.
"""

import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables defined in app.models (idempotent)."""
    # Import here to trigger model registration with Base.metadata
    from app.models import metadata as _  # noqa: F401
    from app.models.metadata import Base

    logger.info("Initializing internal metadata database…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Metadata database initialized.")


async def check_db_health() -> bool:
    """Return True if the internal metadata DB is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        return False
