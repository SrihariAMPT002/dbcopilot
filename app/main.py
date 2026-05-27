"""
FastAPI application factory.

Startup sequence:
  1. Configure logging
  2. Initialize internal metadata DB (create tables if missing)
  3. Mount API router under /api/v1
  4. Serve health and root endpoints
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import check_db_health, init_db

configure_logging()
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated on_event) ───────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("🚀 Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.app_env)
    await init_db()
    yield
    logger.info("🛑 Shutting down %s", settings.app_name)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI Database Copilot — connection infrastructure and schema synchronization. "
            "AI querying endpoints are placeholders for future implementation."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routes ────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.api_prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"], summary="Health check")
    async def health():
        db_ok = await check_db_health()
        return {
            "status": "healthy" if db_ok else "degraded",
            "version": settings.app_version,
            "environment": settings.app_env,
            "db_healthy": db_ok,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/", tags=["System"], include_in_schema=False)
    async def root():
        return JSONResponse(
            {
                "app": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
                "health": "/health",
            }
        )

    return app


app = create_app()
