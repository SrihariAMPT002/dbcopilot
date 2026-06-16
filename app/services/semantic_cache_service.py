"""Semantic cache management for retrieval queries."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic_cache import SemanticCache


class SemanticCacheService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _hash_query(database_id: int, query: str) -> str:
        return hashlib.sha256(f"{database_id}:{query.strip().lower()}".encode("utf-8")).hexdigest()

    async def get(self, database_id: int, query: str) -> Optional[SemanticCache]:
        query_hash = self._hash_query(database_id, query)
        result = await self.db.execute(select(SemanticCache).where(SemanticCache.query_hash == query_hash))
        row = result.scalars().first()
        if not row:
            return None
        if row.ttl_seconds and row.created_at:
            age = (datetime.now(timezone.utc) - row.created_at).total_seconds()
            if age > row.ttl_seconds:
                return None
        row.hit_count = int(row.hit_count or 0) + 1
        row.last_used = datetime.now(timezone.utc)
        await self.db.flush()
        return row

    async def set(
        self,
        *,
        database_id: int,
        query: str,
        response: Any,
        embedding: Optional[list[float]] = None,
        ttl_seconds: int = 3600,
        trace_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> SemanticCache:
        query_hash = self._hash_query(database_id, query)
        result = await self.db.execute(select(SemanticCache).where(SemanticCache.query_hash == query_hash))
        row = result.scalars().first()
        payload = json.dumps(response, ensure_ascii=False, default=str) if not isinstance(response, str) else response
        if row is None:
            row = SemanticCache(
                database_id=database_id,
                query_hash=query_hash,
                query_text=query,
                response=payload,
                embedding=json.dumps(embedding, default=str) if embedding else None,
                ttl_seconds=ttl_seconds,
                last_used=datetime.now(timezone.utc),
                hit_count=0,
                trace_id=trace_id,
                model_name=model_name,
            )
            self.db.add(row)
        else:
            row.response = payload
            row.embedding = json.dumps(embedding, default=str) if embedding else row.embedding
            row.ttl_seconds = ttl_seconds
            row.last_used = datetime.now(timezone.utc)
            row.trace_id = trace_id or row.trace_id
            row.model_name = model_name or row.model_name
        await self.db.flush()
        return row

    async def list(self, database_id: int) -> list[SemanticCache]:
        result = await self.db.execute(select(SemanticCache).where(SemanticCache.database_id == database_id).order_by(SemanticCache.created_at.desc()))
        return list(result.scalars().all())
