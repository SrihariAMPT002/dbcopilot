"""Prompt embeddings for generated prompt packages."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.metadata import Base


class PromptEmbedding(Base):
    __tablename__ = "prompt_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vector: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    prompt_package = relationship("PromptPackage")

