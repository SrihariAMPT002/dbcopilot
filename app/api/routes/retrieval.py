"""Hybrid retrieval APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse, RetrievalHitResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search(request: RetrievalRequest, db: AsyncSession = Depends(get_db)) -> RetrievalResponse:
    try:
        result = await RetrievalService(db).search(request.query, database_id=request.database_id, top_k=request.top_k)
        return RetrievalResponse(
            query=result.query,
            database_id=result.database_id,
            latency_ms=result.latency_ms,
            total_hits=result.total_hits,
            results=[RetrievalHitResponse(**item.__dict__) for item in result.results],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/hybrid", response_model=RetrievalResponse)
async def hybrid(request: RetrievalRequest, db: AsyncSession = Depends(get_db)) -> RetrievalResponse:
    try:
        result = await RetrievalService(db).hybrid_search(request.query, database_id=request.database_id, top_k=request.top_k)
        return RetrievalResponse(
            query=result.query,
            database_id=result.database_id,
            latency_ms=result.latency_ms,
            total_hits=result.total_hits,
            results=[RetrievalHitResponse(**item.__dict__) for item in result.results],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
