"""Retrieval quality evaluation service."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval_evaluation import RetrievalEvaluation


class RetrievalEvaluationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate(
        self,
        *,
        database_id: int,
        query_text: str,
        retrieved_documents: list[dict[str, Any]] | None = None,
        reranked_documents: list[dict[str, Any]] | None = None,
        trace_id: str | None = None,
        model_name: str | None = None,
    ) -> RetrievalEvaluation:
        retrieved_documents = retrieved_documents or []
        reranked_documents = reranked_documents or []
        precision = 1.0 if reranked_documents else 0.0
        recall = min(1.0, len(reranked_documents) / max(1, len(retrieved_documents)))
        mrr = 1.0 if reranked_documents else 0.0
        ndcg = 1.0 if reranked_documents else 0.0
        coverage = min(1.0, len(retrieved_documents) / 10.0)
        hallucination_risk = 0.0 if reranked_documents else 0.5

        evaluation = RetrievalEvaluation(
            database_id=database_id,
            query_text=query_text,
            precision_score=precision,
            recall_score=recall,
            mrr_score=mrr,
            ndcg_score=ndcg,
            coverage_score=coverage,
            hallucination_risk=hallucination_risk,
            evidence=json.dumps(
                {
                    "retrieved_count": len(retrieved_documents),
                    "reranked_count": len(reranked_documents),
                },
                default=str,
            ),
            trace_id=trace_id,
            model_name=model_name,
        )
        self.db.add(evaluation)
        await self.db.flush()
        return evaluation

    async def list(self, database_id: int) -> list[RetrievalEvaluation]:
        result = await self.db.execute(
            select(RetrievalEvaluation).where(RetrievalEvaluation.database_id == database_id).order_by(RetrievalEvaluation.created_at.desc())
        )
        return list(result.scalars().all())
