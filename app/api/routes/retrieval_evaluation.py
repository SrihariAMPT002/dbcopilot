"""Retrieval evaluation APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.retrieval_evaluation import RetrievalEvaluationItem, RetrievalEvaluationListResponse
from app.services.retrieval_evaluation_service import RetrievalEvaluationService

router = APIRouter(prefix="/retrieval/evaluation", tags=["Retrieval Evaluation"])


@router.get("/{database_id}", response_model=RetrievalEvaluationListResponse)
async def list_retrieval_evaluation(database_id: int, db: AsyncSession = Depends(get_db)) -> RetrievalEvaluationListResponse:
    rows = await RetrievalEvaluationService(db).list(database_id)
    return RetrievalEvaluationListResponse(
        database_id=database_id,
        evaluations=[
            RetrievalEvaluationItem(
                id=row.id,
                database_id=row.database_id,
                query_text=row.query_text,
                precision_score=row.precision_score,
                recall_score=row.recall_score,
                mrr_score=row.mrr_score,
                ndcg_score=row.ndcg_score,
                coverage_score=row.coverage_score,
                hallucination_risk=row.hallucination_risk,
                evidence=row.evidence,
                trace_id=row.trace_id,
                model_name=row.model_name,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
