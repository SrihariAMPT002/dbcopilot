"""Column semantic and PII governance APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import ConnectedDatabase, DatabaseColumn, DatabaseSchema, DatabaseTable
from app.schemas.api_schemas import (
    ColumnSemanticResponse,
    GovernancePackageResponse,
    GovernancePiiSummaryResponse,
)
from app.services.column_semantic_service import ColumnSemanticService, ExecutionContext

router = APIRouter(prefix="/column-semantics", tags=["Column Semantics"])
logger = logging.getLogger(__name__)


def _row_to_response(item: ColumnSemantic, column: DatabaseColumn, table: DatabaseTable, schema: DatabaseSchema) -> ColumnSemanticResponse:
    return ColumnSemanticResponse(
        column_id=item.column_id,
        database_id=item.database_id,
        business_name=item.business_name,
        business_description=item.business_description,
        business_meaning=item.business_meaning,
        governance_reasoning=item.governance_reasoning,
        table_purpose=item.table_purpose,
        prompt_id=item.prompt_id,
        prompt_version=item.prompt_version,
        model_name=item.model_name,
        column_category=item.column_category,
        table_category=item.table_category,
        classification_source=item.classification_source,
        is_pii=item.is_pii,
        pii_type=item.pii_type,
        risk_level=item.risk_level,
        confidence_score=item.confidence_score,
        generated_at=item.generated_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        schema_name=schema.name,
        table_name=table.name,
        column_name=column.name,
    )


@router.get("/databases/{db_id}", response_model=list[ColumnSemanticResponse], summary="List column semantics for a database")
async def list_column_semantics(db_id: int, db: AsyncSession = Depends(get_db)) -> list[ColumnSemanticResponse]:
    service = ColumnSemanticService(db)
    await service._fetch_database(db_id)
    result = await db.execute(
        select(ColumnSemantic, DatabaseColumn, DatabaseTable, DatabaseSchema)
        .join(DatabaseColumn, ColumnSemantic.column_id == DatabaseColumn.id)
        .join(DatabaseTable, DatabaseColumn.table_id == DatabaseTable.id)
        .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
        .where(ColumnSemantic.database_id == db_id)
        .order_by(DatabaseSchema.name, DatabaseTable.name, DatabaseColumn.name)
    )
    rows = result.all()
    return [_row_to_response(item, column, table, schema) for item, column, table, schema in rows]


@router.post("/databases/{db_id}/rescan", response_model=list[ColumnSemanticResponse], summary="Rescan and upsert column PII classifications")
async def rescan_column_semantics(
    db_id: int,
    force: bool = Query(default=False, description="Reclassify all columns when true; otherwise only new/changed columns"),
    db: AsyncSession = Depends(get_db),
) -> list[ColumnSemanticResponse]:
    service = ColumnSemanticService(db)
    await service._fetch_database(db_id)
    await service.rescan_database(db_id, force=force)
    await db.commit()
    result = await db.execute(
        select(ColumnSemantic, DatabaseColumn, DatabaseTable, DatabaseSchema)
        .join(DatabaseColumn, ColumnSemantic.column_id == DatabaseColumn.id)
        .join(DatabaseTable, DatabaseColumn.table_id == DatabaseTable.id)
        .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
        .where(ColumnSemantic.database_id == db_id)
        .order_by(DatabaseSchema.name, DatabaseTable.name, DatabaseColumn.name)
    )
    rows = result.all()
    return [_row_to_response(item, column, table, schema) for item, column, table, schema in rows]


@router.get(
    "/databases/{db_id}/governance-package",
    summary="Get aggregated governance intelligence package for a database",
)
async def get_governance_package(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = ColumnSemanticService(db)
    await service._fetch_database(db_id)
    return await service.build_governance_package(db_id)


@router.get(
    "/governance/packages/{database_id}",
    summary="Get canonical governance packages for a database",
    response_model=dict,
)
async def get_governance_packages(database_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = ColumnSemanticService(db)
    await service._fetch_database(database_id)
    return await service.build_governance_package(database_id)


@router.get(
    "/governance/package/{table_id}",
    summary="Get canonical governance package for a table",
    response_model=GovernancePackageResponse,
)
async def get_governance_package_for_table(table_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = ColumnSemanticService(db)
    package = await service.get_governance_package(table_id)
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Governance package not found for table {table_id}")
    return package


@router.get(
    "/governance/pii-summary/{database_id}",
    summary="Get governance PII summary for a database",
    response_model=GovernancePiiSummaryResponse,
)
async def get_governance_pii_summary(database_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    service = ColumnSemanticService(db)
    await service._fetch_database(database_id)
    return await service.get_governance_pii_summary(database_id)


@router.post(
    "/columns/{column_id}/classify",
    response_model=ColumnSemanticResponse,
    summary="Classify a single column for PII and governance",
)
async def classify_column(
    column_id: int,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> ColumnSemanticResponse:
    service = ColumnSemanticService(db)
    try:
        execution_context = ExecutionContext.ADMIN if force else ExecutionContext.MANUAL
        semantic = await service.classify_column(column_id, force=force, execution_context=execution_context)
        await db.commit()
        result = await db.execute(
            select(ColumnSemantic, DatabaseColumn, DatabaseTable, DatabaseSchema)
            .join(DatabaseColumn, ColumnSemantic.column_id == DatabaseColumn.id)
            .join(DatabaseTable, DatabaseColumn.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(ColumnSemantic.column_id == column_id)
        )
        row = result.first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column semantics not found after classification")
        item, column, table, schema = row
        return _row_to_response(item, column, table, schema)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Column classification failed for column_id=%s: %s", column_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to classify column")
