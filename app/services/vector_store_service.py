"""Manage multi-vector collection registry and Qdrant sync."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.vector_collection import VectorCollection
from app.schema_engine.embeddings import get_qdrant_client


CANONICAL_COLLECTIONS = (
    "metadata_vectors",
    "governance_vectors",
    "semantic_vectors",
    "relationship_vectors",
    "kpi_vectors",
    "prompt_vectors",
    "memory_vectors",
)


class VectorStoreService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    async def ensure_collections(self) -> list[VectorCollection]:
        client = get_qdrant_client()
        from qdrant_client.http import models as qmodels

        rows: list[VectorCollection] = []
        for name in CANONICAL_COLLECTIONS:
            existing = await self.db.execute(select(VectorCollection).where(VectorCollection.collection_name == name))
            row = existing.scalars().first()
            if row is None:
                row = VectorCollection(
                    collection_name=name,
                    embedding_model=settings.azure_openai_embedding_deployment,
                    vector_count=0,
                    status="pending",
                    last_synced=None,
                    metadata_json=self._json({"created_by": "vector_store_service"}),
                )
                self.db.add(row)
            try:
                client.get_collection(name)
            except Exception:
                client.create_collection(
                    collection_name=name,
                    vectors_config=qmodels.VectorParams(
                        size=settings.azure_openai_embedding_dimensions or 1536,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
            row.embedding_model = settings.azure_openai_embedding_deployment
            row.status = "healthy"
            row.last_synced = datetime.now(timezone.utc)
            rows.append(row)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            rows = []
            for name in CANONICAL_COLLECTIONS:
                existing = await self.db.execute(select(VectorCollection).where(VectorCollection.collection_name == name))
                row = existing.scalars().first()
                if row is None:
                    row = VectorCollection(
                        collection_name=name,
                        embedding_model=settings.azure_openai_embedding_deployment,
                        vector_count=0,
                        status="pending",
                        last_synced=None,
                        metadata_json=self._json({"created_by": "vector_store_service"}),
                    )
                    self.db.add(row)
                row.embedding_model = settings.azure_openai_embedding_deployment
                row.status = "healthy"
                row.last_synced = datetime.now(timezone.utc)
                rows.append(row)
            await self.db.flush()
        return rows

    async def sync_collection(self, collection_name: str) -> VectorCollection:
        await self.ensure_collections()
        existing = await self.db.execute(select(VectorCollection).where(VectorCollection.collection_name == collection_name))
        row = existing.scalars().first()
        if not row:
            raise ValueError(f"Unknown vector collection {collection_name}")
        client = get_qdrant_client()
        try:
            info = client.get_collection(collection_name)
            row.vector_count = int(info.points_count or 0)
            row.status = "healthy"
        except Exception as exc:
            row.vector_count = 0
            row.status = "failed"
            row.metadata_json = self._json({"error": str(exc)})
        row.last_synced = datetime.now(timezone.utc)
        await self.db.flush()
        return row

    async def rebuild_collections(self) -> list[VectorCollection]:
        rows = await self.ensure_collections()
        for row in rows:
            await self.sync_collection(row.collection_name)
        return rows

    async def delete_vectors(self, collection_name: str) -> None:
        client = get_qdrant_client()
        client.delete_collection(collection_name)

    async def health_status(self) -> list[dict[str, Any]]:
        result = await self.db.execute(select(VectorCollection).order_by(VectorCollection.collection_name))
        rows = result.scalars().all()
        return [
            {
                "collection_name": row.collection_name,
                "embedding_model": row.embedding_model,
                "vector_count": row.vector_count,
                "status": row.status,
                "last_synced": row.last_synced,
            }
            for row in rows
        ]
