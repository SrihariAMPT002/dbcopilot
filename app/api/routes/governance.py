"""Canonical governance package APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import GovernancePackageResponse, GovernancePiiSummaryResponse
from app.services.column_semantic_service import ColumnSemanticService

router = APIRouter(prefix="/governance", tags=["Governance"])


@router.get(
    "/packages/{database_id}",
    response_model=dict,
    summary="Get canonical governance packages for a database",
)
async def get_governance_packages(database_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = ColumnSemanticService(db)
    await service._fetch_database(database_id)
    return await service.build_governance_package(database_id)


@router.get(
    "/package/{table_id}",
    response_model=GovernancePackageResponse,
    summary="Get canonical governance package for a table",
)
async def get_governance_package(table_id: int, db: AsyncSession = Depends(get_db)) -> GovernancePackageResponse:
    service = ColumnSemanticService(db)
    package = await service.get_governance_package(table_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Governance package not found for table {table_id}")
    return GovernancePackageResponse.model_validate(package)


@router.get(
    "/pii-summary/{database_id}",
    response_model=GovernancePiiSummaryResponse,
    summary="Get governance PII summary for a database",
)
async def get_governance_pii_summary(database_id: int, db: AsyncSession = Depends(get_db)) -> GovernancePiiSummaryResponse:
    service = ColumnSemanticService(db)
    await service._fetch_database(database_id)
    summary = await service.get_governance_pii_summary(database_id)
    return GovernancePiiSummaryResponse.model_validate(summary)
