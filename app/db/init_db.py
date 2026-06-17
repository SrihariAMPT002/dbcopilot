"""Database initializer for metadata schema and drift validation."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.db.schema_audit import audit_ai_model_contracts, audit_schema
from app.services.qdrant_service import ensure_required_qdrant_collections

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Apply pending migrations, create missing tables, and validate the live schema."""
    from app.models import metadata as _  # noqa: F401
    from app.models import artifact_manifest as _artifact  # noqa: F401
    from app.models import nosql_metadata as _nosql  # noqa: F401
    from app.models import pipeline_job as _pipeline  # noqa: F401
    from app.models import readiness_snapshot as _readiness  # noqa: F401
    from app.models.metadata import Base

    logger.info("Initializing internal metadata database...")
    async with engine.begin() as conn:
        await conn.run_sync(_apply_pending_migrations)
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_validate_schema_drift)
    ensure_required_qdrant_collections(settings.azure_openai_embedding_dimensions or 1536)
    logger.info("Metadata database initialized.")


def _alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    return cfg


def _apply_pending_migrations(sync_conn) -> None:
    try:
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        current_revision = MigrationContext.configure(sync_conn).get_current_revision()
        head_revision = script.get_current_head()
        logger.info("Alembic migration state current=%s head=%s", current_revision or "none", head_revision or "none")
        if current_revision != head_revision:
            logger.warning("Applying pending Alembic migrations before schema validation")
            cfg.attributes["connection"] = sync_conn
            command.upgrade(cfg, "head")
    except Exception as exc:
        raise RuntimeError(f"Unable to apply Alembic migrations: {exc}") from exc


def _validate_schema_drift(sync_conn) -> None:
    report = audit_schema(sync_conn)
    contract_issues = audit_ai_model_contracts()
    logger.info(
        "Schema audit summary critical=%s warnings=%s manual_review=%s",
        report.has_critical_errors(),
        report.has_warnings(),
        len(report.requires_manual_review),
    )
    if contract_issues:
        logger.warning("AI model contract issues: %s", "; ".join(contract_issues))
    if report.requires_manual_review:
        logger.warning("Schema audit manual review items: %s", "; ".join(report.requires_manual_review))
    for table in report.table_reports:
        if table.extra_columns:
            logger.warning("Schema audit warning extra columns on %s: %s", table.table_name, ", ".join(table.extra_columns))
        if table.missing_indexes:
            logger.warning("Schema audit warning missing indexes on %s: %s", table.table_name, ", ".join(table.missing_indexes))
        if table.duplicate_indexes:
            logger.warning("Schema audit warning duplicate indexes on %s: %s", table.table_name, ", ".join(table.duplicate_indexes))
        if table.missing_unique_constraints:
            logger.warning(
                "Schema audit warning missing unique constraints on %s: %s",
                table.table_name,
                ", ".join(table.missing_unique_constraints),
            )
    if report.has_critical_errors() or report.has_warnings():
        if not settings.strict_schema_validation:
            logger.warning("STRICT_SCHEMA_VALIDATION=false; continuing startup despite schema drift: %s", report.format_message())
            return
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
