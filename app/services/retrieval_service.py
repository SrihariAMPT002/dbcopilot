"""Hybrid retrieval service built on top of embeddings, metadata, and graph context."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.metadata import ConnectedDatabase
from app.services.database_guard import ensure_connected
from app.models.embedding_document import EmbeddingDocument
from app.models.vector_collection import VectorCollection
from app.schema_engine.embeddings import EmbeddingEngine, get_qdrant_client, qmodels
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.semantic_cache_service import SemanticCacheService


@dataclass
class HybridRetrievalHit:
    score: float
    collection: str
    database_id: int
    schema_name: str
    table_name: str
    document_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class HybridRetrievalResult:
    query: str
    database_id: Optional[int]
    latency_ms: float
    total_hits: int
    results: List[HybridRetrievalHit] = field(default_factory=list)


class RetrievalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_engine = EmbeddingEngine(db)
        self.weights = {
            "vector": float(getattr(settings, "retrieval_vector_weight", 0.55) or 0.55),
            "keyword": float(getattr(settings, "retrieval_keyword_weight", 0.20) or 0.20),
            "metadata": float(getattr(settings, "retrieval_metadata_weight", 0.15) or 0.15),
            "graph": float(getattr(settings, "retrieval_graph_weight", 0.10) or 0.10),
        }

    async def _ensure_database(self, database_id: int) -> ConnectedDatabase:
        return await ensure_connected(self.db, database_id)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.split(r"[^a-zA-Z0-9_]+", text.lower()) if token}

    def _keyword_score(self, query: str, content: str) -> float:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0
        content_tokens = self._tokenize(content)
        overlap = len(query_tokens & content_tokens)
        return min(1.0, overlap / max(1, len(query_tokens)))

    def _metadata_score(self, doc: EmbeddingDocument, query: str) -> float:
        haystack = " ".join(
            [
                doc.document_type or "",
                doc.source_package or "",
                doc.content[:2000],
                doc.metadata_json or "",
            ]
        ).lower()
        score = self._keyword_score(query, haystack)
        if doc.document_type == "table_knowledge":
            score += 0.05
        return min(1.0, score)

    def _graph_score(self, doc: EmbeddingDocument) -> float:
        metadata = doc.metadata_json or "{}"
        try:
            parsed = json.loads(metadata)
        except Exception:
            parsed = {}
        boost = 0.0
        if parsed.get("table_name"):
            boost += 0.05
        if parsed.get("schema_name"):
            boost += 0.05
        return min(1.0, boost)

    async def _embedding_search(self, database_id: int, query: str, top_k: int) -> List[Dict[str, Any]]:
        vector, _ = await self.embedding_engine._embed_query(query)
        client = get_qdrant_client()
        if qmodels is None:
            return []
        filt = qmodels.Filter(
            must=[qmodels.FieldCondition(key="database_id", match=qmodels.MatchValue(value=database_id))]
        )
        hits: List[Dict[str, Any]] = []
        for collection in ("metadata_vectors", "governance_vectors", "semantic_vectors", "relationship_vectors", "kpi_vectors", "prompt_vectors", "memory_vectors"):
            try:
                results = client.search(
                    collection_name=collection,
                    query_vector=vector,
                    query_filter=filt,
                    limit=top_k,
                    with_payload=True,
                )
                for item in results:
                    hits.append({"collection": collection, "score": float(item.score or 0.0), "payload": item.payload or {}})
            except Exception:
                continue
        hits.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return hits[:top_k]

    @staticmethod
    def _serialize_result(result: HybridRetrievalResult) -> dict[str, Any]:
        return {
            "query": result.query,
            "database_id": result.database_id,
            "latency_ms": result.latency_ms,
            "total_hits": result.total_hits,
            "results": [
                {
                    "score": hit.score,
                    "collection": hit.collection,
                    "database_id": hit.database_id,
                    "schema_name": hit.schema_name,
                    "table_name": hit.table_name,
                    "document_type": hit.document_type,
                    "content": hit.content,
                    "metadata": hit.metadata,
                    "score_breakdown": hit.score_breakdown,
                }
                for hit in result.results
            ],
        }

    @staticmethod
    def _deserialize_result(payload: dict[str, Any]) -> HybridRetrievalResult:
        results = []
        for item in payload.get("results", []):
            results.append(
                HybridRetrievalHit(
                    score=float(item.get("score", 0.0)),
                    collection=item.get("collection", ""),
                    database_id=int(item.get("database_id") or 0),
                    schema_name=item.get("schema_name", ""),
                    table_name=item.get("table_name", ""),
                    document_type=item.get("document_type", ""),
                    content=item.get("content", ""),
                    metadata=item.get("metadata") or {},
                    score_breakdown=item.get("score_breakdown") or {},
                )
            )
        return HybridRetrievalResult(
            query=payload.get("query", ""),
            database_id=payload.get("database_id"),
            latency_ms=float(payload.get("latency_ms", 0.0) or 0.0),
            total_hits=int(payload.get("total_hits", len(results)) or len(results)),
            results=results,
        )

    async def search(self, query: str, database_id: Optional[int] = None, top_k: int = 5) -> HybridRetrievalResult:
        start = time.perf_counter()
        if database_id is not None:
            await self._ensure_database(database_id)
        cache_service = SemanticCacheService(self.db)
        evaluation_service = RetrievalEvaluationService(self.db)
        if database_id is not None:
            cached = await cache_service.get(database_id, query)
            if cached:
                try:
                    cached_payload = json.loads(cached.response or "{}")
                    result = self._deserialize_result(cached_payload)
                    result.latency_ms = (time.perf_counter() - start) * 1000
                    await evaluation_service.evaluate(
                        database_id=database_id,
                        query_text=query,
                        retrieved_documents=[hit.metadata for hit in result.results],
                        reranked_documents=[],
                        trace_id=cached.trace_id,
                        model_name=cached.model_name,
                    )
                    return result
                except Exception:
                    pass
        embedding_hits = await self._embedding_search(database_id or 0, query, top_k) if database_id is not None else []

        docs_query = select(EmbeddingDocument)
        if database_id is not None:
            docs_query = docs_query.where(EmbeddingDocument.database_id == database_id)
        result = await self.db.execute(docs_query.order_by(EmbeddingDocument.created_at.desc()))
        docs = result.scalars().all()

        scored: List[HybridRetrievalHit] = []
        for doc in docs:
            vector_score = 0.0
            for hit in embedding_hits:
                payload = hit.get("payload") or {}
                if payload.get("table_name") == doc.metadata_json:
                    vector_score = max(vector_score, hit.get("score", 0.0))
            keyword_score = self._keyword_score(query, doc.content)
            metadata_score = self._metadata_score(doc, query)
            graph_score = self._graph_score(doc)
            combined = (
                self.weights["vector"] * vector_score
                + self.weights["keyword"] * keyword_score
                + self.weights["metadata"] * metadata_score
                + self.weights["graph"] * graph_score
            )
            if combined <= 0:
                continue
            scored.append(
                HybridRetrievalHit(
                    score=combined,
                    collection=doc.source_package or doc.document_type,
                    database_id=doc.database_id,
                    schema_name=json.loads(doc.metadata_json or "{}").get("schema_name", ""),
                    table_name=json.loads(doc.metadata_json or "{}").get("table_name", ""),
                    document_type=doc.document_type,
                    content=doc.content,
                    metadata={"document_id": doc.id, "vector_id": doc.vector_id, "trace_id": doc.trace_id},
                    score_breakdown={
                        "vector": round(vector_score, 4),
                        "keyword": round(keyword_score, 4),
                        "metadata": round(metadata_score, 4),
                        "graph": round(graph_score, 4),
                    },
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        scored = scored[:top_k]
        result = HybridRetrievalResult(
            query=query,
            database_id=database_id,
            latency_ms=(time.perf_counter() - start) * 1000,
            total_hits=len(scored),
            results=scored,
        )
        if database_id is not None:
            await cache_service.set(
                database_id=database_id,
                query=query,
                response=self._serialize_result(result),
                ttl_seconds=int(getattr(settings, "semantic_cache_ttl_seconds", 3600) or 3600),
                trace_id=None,
                model_name=settings.azure_openai_deployment,
            )
            await evaluation_service.evaluate(
                database_id=database_id,
                query_text=query,
                retrieved_documents=[hit.metadata for hit in result.results],
                reranked_documents=[],
                trace_id=None,
                model_name=settings.azure_openai_deployment,
            )
        return result

    async def hybrid_search(self, query: str, database_id: Optional[int] = None, top_k: int = 5) -> HybridRetrievalResult:
        return await self.search(query=query, database_id=database_id, top_k=top_k)

    async def filter_search(
        self,
        *,
        query: str,
        database_id: Optional[int] = None,
        document_type: Optional[str] = None,
        source_package: Optional[str] = None,
        top_k: int = 5,
    ) -> HybridRetrievalResult:
        result = await self.search(query=query, database_id=database_id, top_k=max(top_k, 10))
        filtered = []
        for item in result.results:
            if document_type and item.document_type != document_type:
                continue
            if source_package and item.collection != source_package:
                continue
            filtered.append(item)
        return HybridRetrievalResult(
            query=result.query,
            database_id=result.database_id,
            latency_ms=result.latency_ms,
            total_hits=len(filtered),
            results=filtered[:top_k],
        )

    async def cross_database_search(self, query: str, top_k: int = 5) -> HybridRetrievalResult:
        return await self.search(query=query, database_id=None, top_k=top_k)
