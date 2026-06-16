"""Schemas for retrieval evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RetrievalEvaluationItem(BaseModel):
    id: int
    database_id: int
    query_text: str
    precision_score: float
    recall_score: float
    mrr_score: float
    ndcg_score: float
    coverage_score: float
    hallucination_risk: float
    evidence: str
    trace_id: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime


class RetrievalEvaluationListResponse(BaseModel):
    database_id: int
    evaluations: list[RetrievalEvaluationItem]
