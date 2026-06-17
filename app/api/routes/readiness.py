"""
AI readiness APIs.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    ReadinessBreakdownResponse,
    ReadinessCapabilityScore,
    ReadinessCategoryScore,
    ReadinessResponse,
)
from app.services.readiness_service import ReadinessBreakdown, ReadinessService
from app.services.remediation_service import RemediationService
from app.services.cache_service import cache_service
from app.core.structured_logging import api_message, error_message

router = APIRouter(prefix="/readiness", tags=["AI Readiness"])
logger = logging.getLogger(__name__)


def _to_readiness_response(data: ReadinessBreakdown) -> ReadinessResponse:
    return ReadinessResponse(
        database_id=data.database_id,
        database_name=data.database_name,
        readiness_status=data.readiness_status.value,
        generated_at=data.generated_at,
        scores=ReadinessCapabilityScore(
            metadata_score=data.metadata_score,
            semantic_score=data.semantic_score,
            embeddings_score=data.embeddings_score,
            relationship_score=data.relationship_score,
            prompt_score=data.prompt_score,
            kpi_score=data.kpi_readiness_score,
            overall_score=data.overall_score,
        ),
        category_scores=ReadinessCategoryScore(
            metadata_readiness_score=data.metadata_readiness_score,
            semantic_readiness_score=data.semantic_readiness_score,
            relationship_readiness_score=data.relationship_readiness_score,
            ai_context_readiness_score=data.ai_context_readiness_score,
            governance_readiness_score=data.governance_readiness_score,
            kpi_readiness_score=data.kpi_readiness_score,
            overall_score=data.overall_score,
            kpi_cluster_count=data.kpi_cluster_count,
            successful_cluster_count=data.successful_cluster_count,
            failed_cluster_count=data.failed_cluster_count,
            coverage_percentage=data.coverage_percentage,
        ),
        missing_stages=data.missing_stages,
        remediation_hints=data.remediation_hints,
        prompt_id=data.prompt_id,
        prompt_version=data.prompt_version,
        model_name=data.model_name,
        kpi_cluster_count=data.kpi_cluster_count,
        successful_cluster_count=data.successful_cluster_count,
        failed_cluster_count=data.failed_cluster_count,
        coverage_percentage=data.coverage_percentage,
    )


def _to_breakdown_response(data: ReadinessBreakdown) -> ReadinessBreakdownResponse:
    response = _to_readiness_response(data)
    return ReadinessBreakdownResponse(
        **response.model_dump(),
        details=data.details,
        ai_summary=data.ai_summary,
        ai_recommendations=data.ai_recommendations,
        ai_risks=data.ai_risks,
        ai_roadmap=data.ai_roadmap,
        ai_confidence=data.ai_confidence,
    )


@router.get(
    "/{db_id}",
    response_model=ReadinessResponse,
    summary="Get latest AI readiness snapshot for a database",
)
async def get_readiness(db_id: int, db: AsyncSession = Depends(get_db)) -> ReadinessResponse:
    service = ReadinessService(db)
    start = time.perf_counter()
    try:
        cache_key = f"readiness:{db_id}:snapshot"
        cached = await cache_service.get(cache_key)
        if cached:
            payload = ReadinessResponse.model_validate_json(cached)
            logger.info(api_message("readiness get", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
            return payload
        result = await service.get_or_compute(db_id)
        payload = _to_readiness_response(result)
        await cache_service.set(cache_key, payload.model_dump_json(), ttl_seconds=600)
        logger.info(api_message("readiness get", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("readiness lookup failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve readiness status",
        )


@router.get(
    "/{db_id}/breakdown",
    response_model=ReadinessBreakdownResponse,
    summary="Get detailed AI readiness breakdown for a database",
)
async def get_readiness_breakdown(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReadinessBreakdownResponse:
    service = ReadinessService(db)
    start = time.perf_counter()
    try:
        cache_key = f"readiness:{db_id}:breakdown"
        cached = await cache_service.get(cache_key)
        if cached:
            payload = ReadinessBreakdownResponse.model_validate_json(cached)
            logger.info(api_message("readiness breakdown", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
            return payload
        result = await service.get_or_compute(db_id)
        payload = _to_breakdown_response(result)
        await cache_service.set(cache_key, payload.model_dump_json(), ttl_seconds=600)
        logger.info(api_message("readiness breakdown", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("readiness breakdown failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve readiness breakdown",
        )


@router.post(
    "/recompute/{db_id}",
    response_model=ReadinessBreakdownResponse,
    summary="Recompute AI readiness snapshot for a database",
)
async def recompute_readiness(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReadinessBreakdownResponse:
    service = ReadinessService(db)
    start = time.perf_counter()
    try:
        result = await service.recompute(db_id)
        await cache_service.delete(f"readiness:{db_id}:snapshot")
        await cache_service.delete(f"readiness:{db_id}:breakdown")
        logger.info(api_message("readiness recompute", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return _to_breakdown_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("readiness recompute failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recompute readiness",
        )


@router.post(
    "/recalculate/{db_id}",
    response_model=ReadinessBreakdownResponse,
    summary="Recalculate AI readiness snapshot for a database",
)
async def recalculate_readiness(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReadinessBreakdownResponse:
    service = ReadinessService(db)
    start = time.perf_counter()
    try:
        result = await service.recompute(db_id)
        await cache_service.delete(f"readiness:{db_id}:snapshot")
        await cache_service.delete(f"readiness:{db_id}:breakdown")
        logger.info(api_message("readiness recalculate", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return _to_breakdown_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("readiness recalculation failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to recalculate readiness")
