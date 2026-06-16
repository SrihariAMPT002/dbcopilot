"""Schemas for KPI packages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KpiPackageResponse(BaseModel):
    id: int
    database_id: int
    kpi_name: Optional[str] = None
    description: Optional[str] = None
    formula: Optional[str] = None
    category: Optional[str] = None
    confidence_score: float = 0.0
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None
