"""Retrieval metrics API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.embedding_document import EmbeddingDocument
from app.models.retrieval_log import RetrievalLog
from app.models.retrieval_evaluation import RetrievalEvaluation
from app.models.vector_collection import VectorCollection

router = APIRouter(prefix="/retrieval", tags=["Retrieval Metrics"])


@router.get("/metrics/{db_id}")
async def retrieval_metrics(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    docs = await db.execute(select(func.count(EmbeddingDocument.id)).where(EmbeddingDocument.database_id == db_id))
    logs = await db.execute(select(func.count(RetrievalLog.id)).where(RetrievalLog.database_id == db_id))
    evaluations = await db.execute(select(func.count(RetrievalEvaluation.id)).where(RetrievalEvaluation.database_id == db_id))
    collections = await db.execute(select(VectorCollection))
    collection_rows = collections.scalars().all()
    return {
        "database_id": db_id,
        "total_documents": int(docs.scalar() or 0),
        "retrieval_logs": int(logs.scalar() or 0),
        "retrieval_evaluations": int(evaluations.scalar() or 0),
        "collections": [
            {
                "collection_name": row.collection_name,
                "vector_count": row.vector_count,
                "status": row.status,
                "embedding_model": row.embedding_model,
                "last_synced": row.last_synced.isoformat() if row.last_synced else None,
            }
            for row in collection_rows
        ],
    }
