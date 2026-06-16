"""Schemas for reranking responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalHitResponse


class RetrievalRerankRequest(BaseModel):
    query: str
    database_id: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalRerankedHitResponse(BaseModel):
    original: RetrievalHitResponse
    rerank_score: float
    final_score: float
    reasoning: str = ""


class RetrievalRerankResponse(BaseModel):
    query: str
    database_id: Optional[int] = None
    latency_ms: float = 0.0
    trace_id: Optional[str] = None
    model_name: Optional[str] = None
    results: list[RetrievalRerankedHitResponse] = Field(default_factory=list)

