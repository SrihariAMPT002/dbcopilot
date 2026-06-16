"""KPI Intelligence APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.kpi import KpiPackageResponse
from app.services.kpi_intelligence_service import KPIIntelligenceService

router = APIRouter(prefix="/kpi-intelligence", tags=["KPI Intelligence"])
kpi_router = APIRouter(prefix="/kpi", tags=["KPI Intelligence"])
logger = logging.getLogger(__name__)


@router.post("/generate/{db_id}")
async def generate_kpi_intelligence(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = KPIIntelligenceService(db)
    try:
        return await service.generate_for_database(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("KPI intelligence generation failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate KPI intelligence")


@router.get("/{db_id}")
async def get_kpi_intelligence(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = KPIIntelligenceService(db)
    try:
        return await service.get_latest_package(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def _read_kpi_package(db_id: int, db: AsyncSession) -> KpiPackageResponse:
    service = KPIIntelligenceService(db)
    try:
        package = await service.get_package(db_id)
        return KpiPackageResponse.model_validate(package)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/package/{db_id}", response_model=KpiPackageResponse)
async def get_kpi_package(db_id: int, db: AsyncSession = Depends(get_db)) -> KpiPackageResponse:
    return await _read_kpi_package(db_id, db)


@kpi_router.get("/{db_id}", response_model=KpiPackageResponse)
async def get_kpi_package_alias(db_id: int, db: AsyncSession = Depends(get_db)) -> KpiPackageResponse:
    return await _read_kpi_package(db_id, db)
