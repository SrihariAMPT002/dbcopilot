"""Warehouse design proposal model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.metadata import Base


class WarehouseDesign(Base):
    __tablename__ = "warehouse_designs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    database_id: Mapped[int] = mapped_column(Integer, ForeignKey("connected_databases.id", ondelete="CASCADE"), nullable=False, index=True)
    design_name: Mapped[str] = mapped_column(String(255), nullable=False)
    design_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
