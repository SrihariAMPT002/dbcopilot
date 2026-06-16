"""Persisted logs for retrieval and reranking."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_documents: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reranked_documents: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    latency_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    scores: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

