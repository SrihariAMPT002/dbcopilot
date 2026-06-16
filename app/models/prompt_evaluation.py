"""Prompt quality evaluation records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.metadata import Base


class PromptEvaluation(Base):
    __tablename__ = "prompt_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    completeness_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    safety_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    grounding_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    hallucination_risk: Mapped[float] = mapped_column(nullable=False, default=0.0)
    sql_safety_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    rag_quality_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    agent_quality_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    prompt_quality_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    packages_used: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prompt_package = relationship("PromptPackage", back_populates="evaluations")

