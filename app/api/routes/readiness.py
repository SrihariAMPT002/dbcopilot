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
    payload = {
        "database_id": getattr(data, "database_id", 0),
        "database_name": getattr(data, "database_name", "unknown"),
        "readiness_status": getattr(getattr(data, "readiness_status", None), "value", getattr(data, "readiness_status", "unknown")),
        "generated_at": getattr(data, "generated_at", None),
        "scores": {
            "metadata_score": getattr(data, "metadata_score", 0),
            "semantic_score": getattr(data, "semantic_score", 0),
            "embeddings_score": getattr(data, "embeddings_score", 0),
            "relationship_score": getattr(data, "relationship_score", 0),
            "prompt_score": getattr(data, "prompt_score", 0),
            "kpi_score": getattr(data, "kpi_readiness_score", 0),
            "overall_score": getattr(data, "overall_score", 0),
        },
        "category_scores": {
            "metadata_readiness_score": getattr(data, "metadata_readiness_score", 0),
            "semantic_readiness_score": getattr(data, "semantic_readiness_score", 0),
            "relationship_readiness_score": getattr(data, "relationship_readiness_score", 0),
            "ai_context_readiness_score": getattr(data, "ai_context_readiness_score", 0),
            "governance_readiness_score": getattr(data, "governance_readiness_score", 0),
            "kpi_readiness_score": getattr(data, "kpi_readiness_score", 0),
            "overall_score": getattr(data, "overall_score", 0),
            "kpi_cluster_count": getattr(data, "kpi_cluster_count", 0),
            "successful_cluster_count": getattr(data, "successful_cluster_count", 0),
            "failed_cluster_count": getattr(data, "failed_cluster_count", 0),
            "coverage_percentage": getattr(data, "coverage_percentage", 0.0),
        },
        "missing_stages": getattr(data, "missing_stages", []),
        "remediation_hints": getattr(data, "remediation_hints", []),
        "prompt_id": getattr(data, "prompt_id", None),
        "prompt_version": getattr(data, "prompt_version", None),
        "model_name": getattr(data, "model_name", None),
        "kpi_cluster_count": getattr(data, "kpi_cluster_count", 0),
        "successful_cluster_count": getattr(data, "successful_cluster_count", 0),
        "failed_cluster_count": getattr(data, "failed_cluster_count", 0),
        "coverage_percentage": getattr(data, "coverage_percentage", 0.0),
    }
    return ReadinessResponse.model_validate(payload)


def _to_breakdown_response(data: ReadinessBreakdown) -> ReadinessBreakdownResponse:
    response = _to_readiness_response(data)
    return ReadinessBreakdownResponse.model_validate(
        {
            **response.model_dump(),
            "details": getattr(data, "details", {}),
            "ai_summary": getattr(data, "ai_summary", None),
            "ai_recommendations": getattr(data, "ai_recommendations", []),
            "ai_risks": getattr(data, "ai_risks", []),
            "ai_roadmap": getattr(data, "ai_roadmap", []),
            "ai_confidence": getattr(data, "ai_confidence", 0.0),
        }
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
