"""Business event APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.business_event_service import BusinessEventService

router = APIRouter(prefix="/business-events", tags=["Business Events"])


@router.get("/{db_id}")
async def get_business_events(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = BusinessEventService(db)
    try:
        return await service.get_events(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
