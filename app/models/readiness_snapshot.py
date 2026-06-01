"""
AI readiness snapshot model.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class ReadinessStatus(str, enum.Enum):
    NOT_READY = "NOT_READY"
    PARTIAL = "PARTIAL"
    READY = "READY"
    STALE = "STALE"


class ReadinessSnapshot(Base):
    __tablename__ = "readiness_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("connected_databases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metadata_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    semantic_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embeddings_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    readiness_status: Mapped[ReadinessStatus] = mapped_column(
        Enum(ReadinessStatus, name="readiness_status_enum"),
        nullable=False,
        default=ReadinessStatus.NOT_READY,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
