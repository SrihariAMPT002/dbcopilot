"""
AI readiness APIs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    ReadinessBreakdownResponse,
    ReadinessCapabilityScore,
    ReadinessResponse,
)
from app.services.readiness_service import ReadinessBreakdown, ReadinessService

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
            overall_score=data.overall_score,
        ),
        missing_stages=data.missing_stages,
        remediation_hints=data.remediation_hints,
    )


def _to_breakdown_response(data: ReadinessBreakdown) -> ReadinessBreakdownResponse:
    response = _to_readiness_response(data)
    return ReadinessBreakdownResponse(**response.model_dump(), details=data.details)


@router.get(
    "/{db_id}",
    response_model=ReadinessResponse,
    summary="Get latest AI readiness snapshot for a database",
)
async def get_readiness(db_id: int, db: AsyncSession = Depends(get_db)) -> ReadinessResponse:
    service = ReadinessService(db)
    try:
        result = await service.get_or_compute(db_id)
        return _to_readiness_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Readiness lookup failed for db_id=%s: %s", db_id, exc, exc_info=True)
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
    try:
        result = await service.get_or_compute(db_id)
        return _to_breakdown_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Readiness breakdown failed for db_id=%s: %s", db_id, exc, exc_info=True)
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
    try:
        result = await service.recompute(db_id)
        return _to_breakdown_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Readiness recompute failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to recompute readiness",
        )
