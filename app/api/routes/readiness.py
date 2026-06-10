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
    ReadinessCategoryScore,
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
        ),
        missing_stages=data.missing_stages,
        remediation_hints=data.remediation_hints,
        prompt_id=data.prompt_id,
        prompt_version=data.prompt_version,
        model_name=data.model_name,
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
