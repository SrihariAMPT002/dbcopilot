"""Semantic cache APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.semantic_cache import SemanticCacheItem, SemanticCacheListResponse
from app.services.semantic_cache_service import SemanticCacheService

router = APIRouter(prefix="/semantic-cache", tags=["Semantic Cache"])


@router.get("/{database_id}", response_model=SemanticCacheListResponse)
async def list_semantic_cache(database_id: int, db: AsyncSession = Depends(get_db)) -> SemanticCacheListResponse:
    rows = await SemanticCacheService(db).list(database_id)
    return SemanticCacheListResponse(
        database_id=database_id,
        caches=[
            SemanticCacheItem(
                id=row.id,
                database_id=row.database_id,
                query_hash=row.query_hash,
                query_text=row.query_text,
                response=row.response,
                ttl_seconds=row.ttl_seconds,
                last_used=row.last_used,
                hit_count=row.hit_count,
                trace_id=row.trace_id,
                model_name=row.model_name,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
