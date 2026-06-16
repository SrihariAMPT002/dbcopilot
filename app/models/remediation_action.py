"""Readiness remediation actions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    readiness_snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("readiness_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    database_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
