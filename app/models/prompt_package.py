"""Canonical Prompt Studio package model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.metadata import Base


class PromptPackage(Base):
    __tablename__ = "prompt_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    template_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    generated_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    generation_metadata: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    execution_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions = relationship("PromptVersion", back_populates="prompt_package", cascade="all, delete-orphan")
    observability_logs = relationship(
        "PromptObservabilityLog", back_populates="prompt_package", cascade="all, delete-orphan"
    )
    evaluations = relationship("PromptEvaluation", back_populates="prompt_package", cascade="all, delete-orphan")

