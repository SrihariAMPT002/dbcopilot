"""Business event APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.business_event_service import BusinessEventService

router = APIRouter(prefix="/business-events", tags=["Business Events"])


@router.get("/{db_id}")
async def get_business_events(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = BusinessEventService(db)
    return await service.get_events(db_id)
