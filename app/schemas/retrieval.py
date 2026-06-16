"""Schemas for hybrid retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str
    database_id: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalHitResponse(BaseModel):
    score: float
    collection: str
    database_id: int
    schema_name: str
    table_name: str
    document_type: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    query: str
    database_id: Optional[int] = None
    latency_ms: float = 0.0
    total_hits: int = 0
    results: List[RetrievalHitResponse] = Field(default_factory=list)

