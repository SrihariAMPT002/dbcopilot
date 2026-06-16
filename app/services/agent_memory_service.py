"""Agent memory and query history services."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_memory import AgentMemory
from app.models.metadata import ConnectedDatabase
from app.schema_engine.embeddings import get_qdrant_client, qmodels
from app.services.ai_observability_service import AIObservabilityService
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class AgentMemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.vector_store = VectorStoreService(db)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    async def _ensure_database(self, database_id: int) -> ConnectedDatabase:
        database = await self.db.get(ConnectedDatabase, database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def record_memory(
        self,
        *,
        database_id: int,
        query_text: str,
        response_text: str | None = None,
        context_json: dict[str, Any] | None = None,
        memory_type: str = "query_history",
        tags: list[str] | None = None,
        trace_id: str | None = None,
    ) -> AgentMemory:
        await self._ensure_database(database_id)
        await self.vector_store.ensure_collections()
        context_json = context_json or {}
        tags = tags or []
        text_for_embedding = self._build_embedding_text(query_text=query_text, response_text=response_text, context_json=context_json)
        observability = AIObservabilityService()
        ai_result = await observability.generate(
            operation="embeddings",
            module="agent_memory",
            artifact_type="agent_memory",
            prompt_id="agent_memory_embedding",
            prompt_version="1",
            database_id=database_id,
            database_name=None,
            model_name=settings.azure_openai_embedding_deployment or settings.azure_openai_deployment,
            input_texts=[text_for_embedding],
            request_kwargs={},
            extra_metadata={"feature": "agent_memory", "memory_type": memory_type},
        )
        vector = ai_result.embeddings[0] if ai_result.embeddings else []
        memory = AgentMemory(
            database_id=database_id,
            query_text=query_text,
            response_text=response_text,
            context_json=self._json(context_json),
            memory_type=memory_type,
            tags_json=self._json(tags),
            embedding_model=ai_result.model_name,
            vector_id=None,
            trace_id=str(trace_id or ai_result.trace_id or ""),
        )
        self.db.add(memory)
        await self.db.flush()

        if vector:
            memory.vector_id = self._vector_id(memory.id)
            self._upsert_vector(memory=memory, vector=vector, context_json=context_json, tags=tags)
            await self.db.flush()

        return memory

    async def get_history(self, database_id: int, limit: int = 20) -> dict[str, Any]:
        await self._ensure_database(database_id)
        result = await self.db.execute(
            select(AgentMemory)
            .where(AgentMemory.database_id == database_id)
            .order_by(desc(AgentMemory.created_at), desc(AgentMemory.id))
            .limit(limit)
        )
        rows = result.scalars().all()
        return {
            "database_id": database_id,
            "total": len(rows),
            "results": [self._serialize_row(row) for row in rows],
        }

    async def search_history(self, database_id: int, query: str, top_k: int = 5) -> dict[str, Any]:
        await self._ensure_database(database_id)
        await self.vector_store.ensure_collections()
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="embeddings",
            module="agent_memory",
            artifact_type="agent_memory_search",
            prompt_id="agent_memory_search_embedding",
            prompt_version="1",
            database_id=database_id,
            database_name=None,
            model_name=settings.azure_openai_embedding_deployment or settings.azure_openai_deployment,
            input_texts=[query],
            request_kwargs={},
            extra_metadata={"feature": "agent_memory_search"},
        )
        vector = result.embeddings[0] if result.embeddings else []
        if not vector:
            return {"database_id": database_id, "query": query, "total_hits": 0, "results": []}

        client = get_qdrant_client()
        if qmodels is None:
            return {"database_id": database_id, "query": query, "total_hits": 0, "results": []}

        filt = qmodels.Filter(
            must=[qmodels.FieldCondition(key="database_id", match=qmodels.MatchValue(value=database_id))]
        )
        try:
            hits = client.search(
                collection_name="memory_vectors",
                query_vector=vector,
                query_filter=filt,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("Agent memory vector search failed for db_id=%s: %s", database_id, exc)
            hits = []

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "score": float(hit.score or 0.0),
                    "id": int(payload.get("memory_id") or 0),
                    "query_text": payload.get("query_text") or "",
                    "response_text": payload.get("response_text"),
                    "memory_type": payload.get("memory_type") or "query_history",
                    "tags": payload.get("tags") or [],
                    "trace_id": payload.get("trace_id"),
                    "created_at": payload.get("created_at"),
                }
            )
        return {"database_id": database_id, "query": query, "total_hits": len(results), "results": results}

    def _upsert_vector(
        self,
        *,
        memory: AgentMemory,
        vector: list[float],
        context_json: dict[str, Any],
        tags: list[str],
    ) -> None:
        client = get_qdrant_client()
        if qmodels is None:
            raise ImportError("qdrant-client is required for memory vectors")
        payload = {
            "database_id": memory.database_id,
            "memory_id": memory.id,
            "query_text": memory.query_text,
            "response_text": memory.response_text,
            "memory_type": memory.memory_type,
            "tags": tags,
            "context_json": context_json,
            "embedding_model": memory.embedding_model,
            "trace_id": memory.trace_id,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
        }
        client.upsert(
            collection_name="memory_vectors",
            points=[
                qmodels.PointStruct(
                    id=self._vector_id(memory.database_id),
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    @staticmethod
    def _vector_id(memory_id: int) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agent_memory:{memory_id}"))

    @staticmethod
    def _build_embedding_text(*, query_text: str, response_text: str | None, context_json: dict[str, Any]) -> str:
        parts = [f"Query: {query_text.strip()}"]
        if response_text:
            parts.append(f"Response: {response_text.strip()}")
        if context_json:
            parts.append(f"Context: {json.dumps(context_json, ensure_ascii=False, default=str)}")
        return "\n".join(parts)

    @staticmethod
    def _serialize_row(row: AgentMemory) -> dict[str, Any]:
        return {
            "id": row.id,
            "database_id": row.database_id,
            "query_text": row.query_text,
            "response_text": row.response_text,
            "context_json": json.loads(row.context_json or "{}"),
            "memory_type": row.memory_type,
            "tags": json.loads(row.tags_json or "[]"),
            "embedding_model": row.embedding_model,
            "vector_id": row.vector_id,
            "trace_id": row.trace_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
