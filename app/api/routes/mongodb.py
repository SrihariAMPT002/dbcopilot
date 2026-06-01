"""
MongoDB NoSQL inference APIs.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.mongodb_service import MongoDBService

router = APIRouter(prefix="/mongodb", tags=["MongoDB"])
logger = logging.getLogger(__name__)


@router.get("/databases", summary="List MongoDB-connected sources")
async def list_mongodb_databases(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    service = MongoDBService(db)
    rows = await service.list_mongodb_databases()
    return {
        "count": len(rows),
        "databases": [
            {
                "id": row.id,
                "name": row.name,
                "database_name": row.database_name,
                "status": row.status.value,
                "last_sync_at": row.last_sync_at,
            }
            for row in rows
        ],
    }


@router.get("/collections/{db_id}", summary="List inferred MongoDB collections")
async def list_collections(db_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    service = MongoDBService(db)
    try:
        await service.ensure_collection_registry(db_id)
        rows = await service.list_collections(db_id)
        return {
            "database_id": db_id,
            "count": len(rows),
            "collections": [
                {
                    "id": row.id,
                    "name": row.name,
                    "table_id": row.table_id,
                    "document_count": row.document_count,
                    "sampled_documents": row.sampled_documents,
                    "schema_confidence": row.schema_confidence,
                    "inferred_at": row.inferred_at,
                }
                for row in rows
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/schema/{collection_id}", summary="Get inferred schema for a collection")
async def get_collection_schema(
    collection_id: int,
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = MongoDBService(db)
    try:
        collection, fields = await service.get_collection_schema(collection_id, limit=limit, offset=offset)
        payload = []
        for item in fields:
            payload.append(
                {
                    "id": item.id,
                    "field_path": item.field_path,
                    "inferred_data_type": item.inferred_data_type,
                    "nested_depth": item.nested_depth,
                    "is_array": item.is_array,
                    "occurrence_percentage": item.occurrence_percentage,
                    "schema_confidence": item.schema_confidence,
                    "type_distribution": json.loads(item.type_distribution or "{}"),
                    "inferred_at": item.inferred_at,
                }
            )
        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "schema_confidence": collection.schema_confidence,
            "sampled_documents": collection.sampled_documents,
            "fields": payload,
            "pagination": {"limit": limit, "offset": offset, "count": len(payload)},
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/sample/{collection_id}", summary="Get sampled documents for a collection")
async def get_collection_samples(
    collection_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = MongoDBService(db)
    try:
        collection, samples = await service.get_collection_samples(collection_id, limit=limit, offset=offset)
        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "samples": [
                {
                    "id": item.id,
                    "sample_index": item.sample_index,
                    "sample_document": json.loads(item.sample_document),
                    "sampled_at": item.sampled_at,
                }
                for item in samples
            ],
            "pagination": {"limit": limit, "offset": offset, "count": len(samples)},
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/infer-schema/{collection_id}", summary="Run schema inference for a Mongo collection")
async def infer_collection_schema(
    collection_id: int,
    sample_size: int = Query(default=100, ge=10, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = MongoDBService(db)
    try:
        payload = await service.infer_schema(collection_id, sample_size=sample_size)
        return {
            "collection_id": collection_id,
            "status": "completed",
            "sampled_documents": payload.get("sampled_documents", 0),
            "schema_confidence": payload.get("schema_confidence", 0.0),
            "field_count": len(payload.get("fields", [])),
            "relationship_count": len(payload.get("relationships", [])),
            "message": "MongoDB schema inference completed",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Mongo inference failed for collection_id=%s: %s", collection_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MongoDB schema inference failed",
        )


@router.get("/relationships/{collection_id}", summary="Get inferred relationships for a collection")
async def get_collection_relationships(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = MongoDBService(db)
    try:
        collection, rels = await service.get_relationships(collection_id)
        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "relationships": [
                {
                    "id": item.id,
                    "source_field_path": item.source_field_path,
                    "target_collection_name": item.target_collection_name,
                    "target_field_path": item.target_field_path,
                    "relationship_type": item.relationship_type,
                    "confidence_score": item.confidence_score,
                    "evidence_count": item.evidence_count,
                    "inferred_at": item.inferred_at,
                }
                for item in rels
            ],
            "count": len(rels),
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
