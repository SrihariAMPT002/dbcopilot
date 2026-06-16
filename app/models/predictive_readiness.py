"""Predictive readiness package model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class PredictiveReadiness(Base):
    __tablename__ = "predictive_readiness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_readiness_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    text_to_sql_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    rag_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    analytics_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    forecasting_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    anomaly_detection_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    ml_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    agent_capabilities: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
