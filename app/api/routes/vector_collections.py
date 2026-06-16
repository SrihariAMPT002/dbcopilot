"""Vector collection management APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.vector_collection import VectorCollectionItem, VectorCollectionListResponse
from app.services.vector_store_service import VectorStoreService

router = APIRouter(prefix="/embeddings/collections", tags=["Vector Collections"])


@router.get("", response_model=VectorCollectionListResponse)
async def list_vector_collections(db: AsyncSession = Depends(get_db)) -> VectorCollectionListResponse:
    service = VectorStoreService(db)
    collections = await service.health_status()
    return VectorCollectionListResponse(
        collections=[VectorCollectionItem(**item) for item in collections]
    )


@router.post("/ensure", response_model=VectorCollectionListResponse)
async def ensure_vector_collections(db: AsyncSession = Depends(get_db)) -> VectorCollectionListResponse:
    service = VectorStoreService(db)
    try:
        rows = await service.ensure_collections()
        return VectorCollectionListResponse(
            collections=[
                VectorCollectionItem(
                    collection_name=row.collection_name,
                    embedding_model=row.embedding_model,
                    vector_count=row.vector_count,
                    status=row.status,
                    last_synced=row.last_synced,
                )
                for row in rows
            ]
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

