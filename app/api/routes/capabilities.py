"""
Capability discovery endpoints.

Exposes mounted platform capability states so the frontend can adapt workflows
without hardcoding assumptions.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.schema_engine.embeddings import EmbeddingEngine

CapabilityState = Literal["enabled", "disabled", "experimental", "not_implemented"]

router = APIRouter(tags=["Capabilities"])


def _state(enabled: bool, *, experimental: bool = False) -> CapabilityState:
    if enabled:
        return "experimental" if experimental else "enabled"
    return "disabled"


@router.get(
    "/capabilities",
    summary="Discover backend capability availability and lifecycle state",
)
async def get_capabilities(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, bool | CapabilityState]]:
    embedding_engine = EmbeddingEngine(db)
    embeddings_enabled = embedding_engine.is_embedding_ready() and embedding_engine.is_qdrant_ready()

    capabilities = {
        "semantic_intelligence": {
            "enabled": True,
            "state": _state(True),
        },
        "embeddings": {
            "enabled": embeddings_enabled,
            "state": _state(embeddings_enabled),
        },
        "relationships": {
            "enabled": True,
            "state": _state(True),
        },
        "exports": {
            "enabled": True,
            "state": _state(True, experimental=True),
        },
        "metadata": {
            "enabled": True,
            "state": _state(True),
        },
        "sync": {
            "enabled": True,
            "state": _state(True),
        },
        "readiness": {
            "enabled": True,
            "state": "experimental",
        },
        "ai_placeholders": {
            "enabled": False,
            "state": "disabled",
        },
        "operations": {
            "enabled": True,
            "state": "experimental",
        },
        "artifact_registry": {
            "enabled": True,
            "state": "experimental",
        },
        "mongodb_inference": {
            "enabled": True,
            "state": "experimental",
        },
    }

    return capabilities
