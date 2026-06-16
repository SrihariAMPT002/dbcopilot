"""Retrieval quality evaluation records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class RetrievalEvaluation(Base):
    __tablename__ = "retrieval_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    precision_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    recall_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    mrr_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    ndcg_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    coverage_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    hallucination_risk: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
