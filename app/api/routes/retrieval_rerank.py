"""Reranking API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.retrieval_rerank import RetrievalRerankRequest, RetrievalRerankResponse, RetrievalRerankedHitResponse
from app.schemas.retrieval import RetrievalHitResponse
from app.services.retrieval_reranker_service import RetrievalRerankerService

router = APIRouter(prefix="/retrieval", tags=["Retrieval Rerank"])


@router.post("/rerank", response_model=RetrievalRerankResponse)
async def rerank(request: RetrievalRerankRequest, db: AsyncSession = Depends(get_db)) -> RetrievalRerankResponse:
    result = await RetrievalRerankerService(db).rerank(
        query=request.query,
        database_id=request.database_id,
        top_k=request.top_k,
    )
    return RetrievalRerankResponse(
        query=result.query,
        database_id=result.database_id,
        latency_ms=result.latency_ms,
        trace_id=result.trace_id,
        model_name=result.model_name,
        results=[
            RetrievalRerankedHitResponse(
                original=RetrievalHitResponse(**item.original.__dict__),
                rerank_score=item.rerank_score,
                final_score=item.final_score,
                reasoning=item.reasoning,
            )
            for item in result.results
        ],
    )

