"""Business insight APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.business_insight_service import BusinessInsightService

router = APIRouter(prefix="/business-insights", tags=["Business Insights"])


@router.get("/{db_id}")
async def get_business_insights(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = BusinessInsightService(db)
    return await service.get_insights(db_id)
