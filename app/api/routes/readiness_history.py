"""Readiness history APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.readiness_snapshot import ReadinessSnapshot
from app.schemas.api_schemas import ReadinessBreakdownResponse, ReadinessResponse

router = APIRouter(prefix="/readiness/history", tags=["AI Readiness History"])


@router.get("/{db_id}")
async def readiness_history(
    db_id: int,
    db: AsyncSession = Depends(get_db),
    maturity_level: str | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    max_score: int | None = Query(default=None, ge=0, le=100),
) -> dict:
    query = select(ReadinessSnapshot).where(ReadinessSnapshot.database_id == db_id)
    if maturity_level:
        query = query.where(ReadinessSnapshot.readiness_status == maturity_level)
    if min_score is not None:
        query = query.where(ReadinessSnapshot.overall_score >= min_score)
    if max_score is not None:
        query = query.where(ReadinessSnapshot.overall_score <= max_score)
    result = await db.execute(query.order_by(ReadinessSnapshot.generated_at.desc()))
    rows = result.scalars().all()
    return {
        "database_id": db_id,
        "snapshots": [
            {
                "id": row.id,
                "database_id": row.database_id,
                "overall_score": row.overall_score,
                "maturity_level": row.readiness_status.value,
                "summary": row.ai_summary,
                "confidence_score": row.ai_confidence,
                "trace_id": row.trace_id,
                "model_name": row.model_name,
                "generated_at": row.generated_at,
            }
            for row in rows
        ],
    }
