"""
Schema retrieval engine.

Performs semantic search over the Qdrant collections populated by the
embedding pipeline and returns relevant tables, relationships, and prompt
contexts for a natural-language query.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import ConnectedDatabase
from app.schema_engine.embeddings import (
    COLLECTION_SCHEMA_PROMPTS,
    COLLECTION_SCHEMA_RELATIONSHIPS,
    COLLECTION_SCHEMA_TABLES,
    EMBEDDING_COLLECTIONS,
    EmbeddingEngine,
    get_qdrant_client,
    qmodels,
    _traceable,
)
from app.utils import truncate

logger = logging.getLogger(__name__)


@dataclass
class RetrievalHit:
    score: float
    collection: str
    database_id: int
    table_id: int
    schema_id: int
    schema_name: str
    table_name: str
    table_type: str | None = None
    matched_text: str = ""
    columns: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    prompt_context: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    query: str
    database_id: int
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    tables: List[RetrievalHit] = field(default_factory=list)
    relationships: List[RetrievalHit] = field(default_factory=list)
    prompt_contexts: List[RetrievalHit] = field(default_factory=list)

    @property
    def total_hits(self) -> int:
        return len(self.tables) + len(self.relationships) + len(self.prompt_contexts)


class RetrievalEngine:
    """Semantic search across schema vectors."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_engine = EmbeddingEngine(db)

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _embed_query(self, query: str) -> tuple[list[float], Dict[str, int]]:
        return await self.embedding_engine._embed_text(query)

    def _query_filter(self, database_id: int):
        if qmodels is None:
            raise ImportError("qdrant-client is required for semantic retrieval")
        return qmodels.Filter(
            must=[qmodels.FieldCondition(key="database_id", match=qmodels.MatchValue(value=database_id))]
        )

    def _to_hit(self, collection_name: str, item: Any) -> RetrievalHit:
        payload = item.payload or {}
        metadata = {k: v for k, v in payload.items() if k not in {"text", "prompt_context"}}
        return RetrievalHit(
            score=float(item.score or 0.0),
            collection=collection_name,
            database_id=int(payload.get("database_id", 0) or 0),
            table_id=int(payload.get("table_id", 0) or 0),
            schema_id=int(payload.get("schema_id", 0) or 0),
            schema_name=str(payload.get("schema_name", "")),
            table_name=str(payload.get("table_name", "")),
            table_type=payload.get("table_type"),
            matched_text=truncate(str(payload.get("text", "")), 800),
            columns=list(payload.get("column_names", [])),
            relationships=[
                rel if isinstance(rel, str) else self._format_relationship(rel)
                for rel in payload.get("relationships", [])
            ],
            prompt_context=payload.get("prompt_context"),
            metadata=metadata,
        )

    def _format_relationship(self, rel: Dict[str, Any]) -> str:
        target_schema = f"{rel.get('referenced_schema')}." if rel.get("referenced_schema") else ""
        constraint = f" ({rel.get('constraint_name')})" if rel.get("constraint_name") else ""
        return (
            f"{rel.get('column_name')} -> "
            f"{target_schema}{rel.get('referenced_table_name')}.{rel.get('referenced_column_name')}{constraint}"
        )

    @_traceable("semantic_search", run_type="retriever")
    async def search(self, database_id: int, query: str, top_k: int = 5) -> RetrievalResult:
        start = time.perf_counter()
        await self._fetch_database(database_id)
        vector, usage = await self._embed_query(query)

        client = get_qdrant_client()
        query_filter = self._query_filter(database_id)

        table_hits: List[RetrievalHit] = []
        relationship_hits: List[RetrievalHit] = []
        prompt_hits: List[RetrievalHit] = []

        search_specs = [
            (COLLECTION_SCHEMA_TABLES, table_hits),
            (COLLECTION_SCHEMA_RELATIONSHIPS, relationship_hits),
            (COLLECTION_SCHEMA_PROMPTS, prompt_hits),
        ]

        for collection_name, bucket in search_specs:
            results = client.search(
                collection_name=collection_name,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_k,
            )
            bucket.extend(self._to_hit(collection_name, item) for item in results)

        result = RetrievalResult(
            query=query,
            database_id=database_id,
            latency_ms=(time.perf_counter() - start) * 1000,
            token_usage=usage,
            tables=table_hits,
            relationships=relationship_hits,
            prompt_contexts=prompt_hits,
        )
        logger.info(
            "Semantic search db_id=%s query=%r returned %d hits in %.2fms",
            database_id,
            query[:100],
            result.total_hits,
            result.latency_ms,
        )
        return result

    async def status_snapshot(self, database_id: int) -> Dict[str, Any]:
        return await self.embedding_engine.get_embedding_status(database_id)
