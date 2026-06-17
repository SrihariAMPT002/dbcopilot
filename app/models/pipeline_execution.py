"""Pipeline execution tracking models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.metadata import Base


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_usage_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    used_context: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_truncated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stages = relationship("StageExecution", back_populates="pipeline_execution", cascade="all, delete-orphan")


class StageExecution(Base):
    __tablename__ = "stage_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_execution_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pipeline_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    database_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_usage_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    used_context: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_truncated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    pipeline_execution = relationship("PipelineExecution", back_populates="stages")
