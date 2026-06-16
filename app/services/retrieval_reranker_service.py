"""LLM-based reranking for hybrid retrieval results."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.retrieval_log import RetrievalLog
from app.services.ai_observability_service import AIObservabilityService
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.retrieval_service import HybridRetrievalHit, HybridRetrievalResult, RetrievalService


@dataclass
class RerankedRetrievalHit:
    original: HybridRetrievalHit
    rerank_score: float
    final_score: float
    reasoning: str = ""


@dataclass
class RerankedRetrievalResult:
    query: str
    database_id: Optional[int]
    latency_ms: float
    trace_id: Optional[str]
    model_name: Optional[str]
    results: List[RerankedRetrievalHit] = field(default_factory=list)


class RetrievalRerankerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.retrieval_service = RetrievalService(db)

    @staticmethod
    def _compact(items: List[HybridRetrievalHit]) -> str:
        payload = []
        for item in items:
            payload.append(
                {
                    "collection": item.collection,
                    "database_id": item.database_id,
                    "schema_name": item.schema_name,
                    "table_name": item.table_name,
                    "document_type": item.document_type,
                    "score": item.score,
                    "content": item.content[:1200],
                }
            )
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _extract_score(text: str) -> float:
        try:
            data = json.loads(text)
            score = float(data.get("score", 0.0))
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    async def rerank(self, query: str, database_id: Optional[int] = None, top_k: int = 5) -> RerankedRetrievalResult:
        start = time.perf_counter()
        base_result = await self.retrieval_service.hybrid_search(query=query, database_id=database_id, top_k=max(top_k, 10))
        candidates = base_result.results
        observability = AIObservabilityService()
        prompt = {
            "query": query,
            "candidates": self._compact(candidates),
            "instructions": (
                "Return JSON only with a numeric score between 0 and 1 and a short reason. "
                "Prefer semantic relevance, governance alignment, relationship proximity, and business context."
            ),
        }
        result = await observability.generate(
            operation="chat",
            module="retrieval",
            artifact_type="rerank",
            prompt_id="retrieval_reranker",
            prompt_version="1.0",
            database_id=database_id,
            database_name=None,
            model_name=settings.azure_openai_deployment or "gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a retrieval reranking engine. Return compact JSON only."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, indent=2)},
            ],
            request_kwargs={},
            extra_metadata={"feature": "retrieval_rerank"},
        )
        content = result.content or ""
        rerank_score = self._extract_score(content)
        reranked: List[RerankedRetrievalHit] = []
        for hit in candidates[:top_k]:
            final_score = 0.7 * hit.score + 0.3 * rerank_score
            reranked.append(
                RerankedRetrievalHit(
                    original=hit,
                    rerank_score=rerank_score,
                    final_score=final_score,
                    reasoning=content[:500],
                )
            )
        reranked.sort(key=lambda item: item.final_score, reverse=True)
        log = RetrievalLog(
            database_id=database_id,
            query=query,
            retrieved_documents=self._compact(candidates[:top_k]),
            reranked_documents=self._compact([item.original for item in reranked]),
            latency_ms=(time.perf_counter() - start) * 1000,
            scores=json.dumps({"rerank_score": rerank_score}, default=str),
            trace_id=result.trace_id,
            model_name=result.model_name,
        )
        self.db.add(log)
        await RetrievalEvaluationService(self.db).evaluate(
            database_id=database_id or 0,
            query_text=query,
            retrieved_documents=[hit.metadata for hit in candidates],
            reranked_documents=[item.original.metadata for item in reranked],
            trace_id=result.trace_id,
            model_name=result.model_name,
        )
        await self.db.commit()
        return RerankedRetrievalResult(
            query=query,
            database_id=database_id,
            latency_ms=log.latency_ms or 0.0,
            trace_id=result.trace_id,
            model_name=result.model_name,
            results=reranked,
        )
