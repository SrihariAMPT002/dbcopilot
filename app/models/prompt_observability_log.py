"""Observability for prompt generation and optimization."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.metadata import Base


class PromptObservabilityLog(Base):
    __tablename__ = "prompt_observability_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    execution_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prompt_package = relationship("PromptPackage", back_populates="observability_logs")

