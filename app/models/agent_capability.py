"""Agent capability package model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class AgentCapability(Base):
    __tablename__ = "agent_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_name: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
