"""KPI Intelligence APIs."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.kpi import KpiPackageResponse
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.cache_service import cache_service
from app.core.structured_logging import api_message, error_message

router = APIRouter(prefix="/kpi-intelligence", tags=["KPI Intelligence"])
logger = logging.getLogger(__name__)


@router.post("/generate/{db_id}")
async def generate_kpi_intelligence(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = KPIIntelligenceService(db)
    start = time.perf_counter()
    try:
        result = await service.generate_for_database(db_id)
        logger.info(api_message("kpi generate", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("kpi intelligence generation failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate KPI intelligence")


@router.get("/{db_id}")
async def get_kpi_intelligence(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = KPIIntelligenceService(db)
    start = time.perf_counter()
    try:
        cache_key = f"kpi:{db_id}:latest"
        cached = await cache_service.get(cache_key)
        if cached:
            logger.info(api_message("kpi latest package", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
            return json.loads(cached)
        result = await service.get_latest_package(db_id)
        await cache_service.set(cache_key, json.dumps(result, default=str), ttl_seconds=600)
        logger.info(api_message("kpi latest package", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def _read_kpi_package(db_id: int, db: AsyncSession) -> KpiPackageResponse:
    service = KPIIntelligenceService(db)
    try:
        cache_key = f"kpi:{db_id}:package"
        cached = await cache_service.get(cache_key)
        if cached:
            return KpiPackageResponse.model_validate_json(cached)
        package = await service.get_package(db_id)
        response = KpiPackageResponse.model_validate({**package, "cache_status": "live"})
        await cache_service.set(cache_key, response.model_dump_json(), ttl_seconds=600)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/package/{db_id}", response_model=KpiPackageResponse)
async def get_kpi_package(db_id: int, db: AsyncSession = Depends(get_db)) -> KpiPackageResponse:
    return await _read_kpi_package(db_id, db)

