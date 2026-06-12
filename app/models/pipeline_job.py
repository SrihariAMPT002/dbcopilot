"""
Pipeline job model for operational visibility.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class JobType(str, enum.Enum):
    ai_context = "AI_CONTEXT"
    metadata_normalization = "METADATA_NORMALIZATION"
    sync = "SYNC"
    semantic = "SEMANTIC_ENRICHMENT"
    prompt = "PROMPT_GENERATION"
    embeddings = "EMBEDDINGS"
    exports = "EXPORTS"
    artifact_packaging = "ARTIFACT_PACKAGING"
    readiness = "READINESS"
    relationship_graph = "RELATIONSHIP_GRAPH"
    kpi = "KPI_INTELLIGENCE"


class JobStatus(str, enum.Enum):
    queued = "QUEUED"
    running = "RUNNING"
    failed = "FAILED"
    completed = "COMPLETED"
    cancelled = "CANCELLED"


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_job_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("pipeline_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="pipeline_job_type_enum"),
        nullable=False,
        index=True,
    )
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_table_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("database_tables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="pipeline_job_status_enum"),
        nullable=False,
        default=JobStatus.queued,
        index=True,
    )
    progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    depends_on: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
