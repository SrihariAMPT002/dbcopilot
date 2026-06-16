"""Schemas for vector collection registry."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VectorCollectionItem(BaseModel):
    collection_name: str
    embedding_model: Optional[str] = None
    vector_count: int = 0
    status: str
    last_synced: Optional[datetime] = None


class VectorCollectionListResponse(BaseModel):
    collections: list[VectorCollectionItem] = Field(default_factory=list)

