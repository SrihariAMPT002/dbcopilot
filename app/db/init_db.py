"""
Database initializer — creates all metadata tables on first startup.
Called from the FastAPI lifespan handler.
"""

import logging

from sqlalchemy import text

from app.db.session import engine
from app.db.schema_audit import audit_schema

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables defined in app.models (idempotent)."""
    # Import here to trigger model registration with Base.metadata
    from app.models import metadata as _  # noqa: F401
    from app.models import readiness_snapshot as _readiness  # noqa: F401
    from app.models import pipeline_job as _pipeline  # noqa: F401
    from app.models import artifact_manifest as _artifact  # noqa: F401
    from app.models import nosql_metadata as _nosql  # noqa: F401
    from app.models.metadata import Base

    logger.info("Initializing internal metadata database…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_validate_schema_drift)
    logger.info("Metadata database initialized.")


def _validate_schema_drift(sync_conn) -> None:
    report = audit_schema(sync_conn)
    if report.requires_manual_review:
        for item in report.requires_manual_review:
            logger.warning("Schema audit manual review: %s", item)
    if report.has_errors or report.requires_manual_review:
        raise RuntimeError(report.format_message())


async def check_db_health() -> bool:
    """Return True if the internal metadata DB is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        return False
