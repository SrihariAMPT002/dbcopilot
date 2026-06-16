"""Schemas for semantic cache."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SemanticCacheItem(BaseModel):
    id: int
    database_id: int
    query_hash: str
    query_text: str
    response: str
    ttl_seconds: int
    last_used: Optional[datetime] = None
    hit_count: int
    trace_id: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime


class SemanticCacheListResponse(BaseModel):
    database_id: int
    caches: list[SemanticCacheItem]
