"""Business event schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class BusinessEventItemResponse(BaseModel):
    id: int
    event_name: str
    event_type: Optional[str] = None
    source_tables: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None


class BusinessEventListResponse(BaseModel):
    database_id: int
    events: List[BusinessEventItemResponse] = Field(default_factory=list)


class BusinessEventHealthResponse(BaseModel):
    database_id: int
    event_rows: int
    latest_trace_id: Optional[str] = None
    state: str
