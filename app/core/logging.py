"""
Structured logging setup.
Call configure_logging() once at application startup.
"""

import logging
import sys
from typing import Optional

from app.core.config import settings


def configure_logging(level: Optional[str] = None) -> None:
    log_level = getattr(logging, level or settings.log_level, logging.INFO)

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        if settings.is_development
        else "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("alembic").setLevel(logging.WARNING)

    sql_level = logging.CRITICAL if settings.api_log_only else (logging.INFO if settings.sql_debug_enabled else logging.CRITICAL)
    for noisy in ("sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.dialects", "asyncpg"):
        logging.getLogger(noisy).setLevel(sql_level)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
