"""
Capability discovery endpoints.

Exposes mounted platform capability states so the frontend can adapt workflows
without hardcoding assumptions.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.package_registry import get_package_registry
from app.config.package_registry import package_is_enabled
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
    registry = get_package_registry()
    packages = registry.get("packages", {}) if isinstance(registry, dict) else {}
    package_flags = {
        name: bool(data.get("enabled", False))
        for name, data in packages.items()
        if isinstance(data, dict)
    }
    embedding_engine = EmbeddingEngine(db)
    embeddings_enabled = embedding_engine.is_embedding_ready() and embedding_engine.is_qdrant_ready()

    capabilities = {
        "semantic_intelligence": {
            "enabled": package_flags.get("semantic", package_is_enabled("semantic")),
            "state": _state(package_flags.get("semantic", package_is_enabled("semantic"))),
        },
        "embeddings": {
            "enabled": embeddings_enabled,
            "state": _state(embeddings_enabled),
        },
        "relationships": {
            "enabled": package_flags.get("relationship", package_is_enabled("relationship")),
            "state": _state(package_flags.get("relationship", package_is_enabled("relationship"))),
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
            "enabled": package_flags.get("governance", package_is_enabled("governance")),
            "state": "experimental" if package_flags.get("governance", package_is_enabled("governance")) else "disabled",
        },
        "ai_placeholders": {
            "enabled": False,
            "state": "disabled",
        },
        "operations": {
            "enabled": package_flags.get("agent", package_is_enabled("agent")),
            "state": "experimental" if package_flags.get("agent", package_is_enabled("agent")) else "disabled",
        },
        "artifact_registry": {
            "enabled": package_flags.get("agent", package_is_enabled("agent")),
            "state": "experimental" if package_flags.get("agent", package_is_enabled("agent")) else "disabled",
        },
        "mongodb_inference": {
            "enabled": True,
            "state": "experimental",
        },
    }

    return capabilities


@router.get(
    "/config/packages",
    summary="Return package registry metadata for the UI",
)
async def get_packages_config() -> dict[str, object]:
    return get_package_registry()
