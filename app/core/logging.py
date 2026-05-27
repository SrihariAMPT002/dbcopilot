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

    # Silence noisy third-party loggers
    for noisy in ("asyncio", "sqlalchemy.engine", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
