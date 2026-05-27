"""
Metadata read endpoints — browse the discovered schema hierarchy.

GET /metadata/databases/{db_id}/schemas
GET /metadata/schemas/{schema_id}/tables
GET /metadata/tables/{table_id}/columns
GET /metadata/tables/{table_id}/relationships
GET /metadata/databases/{db_id}/sync-logs
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    SyncLog,
)
from app.schemas.api_schemas import (
    ColumnResponse,
    RelationshipResponse,
    SchemaResponse,
    SyncLogResponse,
    TableResponse,
)

router = APIRouter(prefix="/metadata", tags=["Schema Metadata"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

@router.get(
    "/databases/{db_id}/schemas",
    response_model=List[SchemaResponse],
    summary="List schemas for a connected database",
)
async def list_schemas(db_id: int, db: AsyncSession = Depends(get_db)):
    # Verify DB exists
    conn = await db.get(ConnectedDatabase, db_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection id={db_id} not found")

    result = await db.execute(
        select(DatabaseSchema)
        .options(selectinload(DatabaseSchema.tables))
        .where(DatabaseSchema.connected_db_id == db_id)
        .order_by(DatabaseSchema.name)
    )
    schemas = result.scalars().all()

    # Build responses inside session (while tables are loaded)
    return [
        SchemaResponse(
            id=s.id,
            connected_db_id=s.connected_db_id,
            name=s.name,
            description=s.description,
            created_at=s.created_at,
            table_count=len(s.tables) if s.tables else 0,
        )
        for s in schemas
    ]


# ── Tables ────────────────────────────────────────────────────────────────────

@router.get(
    "/schemas/{schema_id}/tables",
    response_model=List[TableResponse],
    summary="List tables within a schema",
)
async def list_tables(schema_id: int, db: AsyncSession = Depends(get_db)):
    schema = await db.get(DatabaseSchema, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema id={schema_id} not found")

    result = await db.execute(
        select(DatabaseTable)
        .options(selectinload(DatabaseTable.columns))
        .where(DatabaseTable.schema_id == schema_id)
        .order_by(DatabaseTable.name)
    )
    tables = result.scalars().all()

    # Build responses inside session (while columns are loaded)
    return [
        TableResponse(
            id=t.id,
            schema_id=t.schema_id,
            name=t.name,
            table_type=t.table_type.value,
            row_count=t.row_count,
            description=t.description,
            created_at=t.created_at,
            column_count=len(t.columns) if t.columns else 0,
        )
        for t in tables
    ]


# ── Columns ───────────────────────────────────────────────────────────────────

@router.get(
    "/tables/{table_id}/columns",
    response_model=List[ColumnResponse],
    summary="List columns within a table",
)
async def list_columns(table_id: int, db: AsyncSession = Depends(get_db)):
    table = await db.get(DatabaseTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table id={table_id} not found")

    result = await db.execute(
        select(DatabaseColumn)
        .where(DatabaseColumn.table_id == table_id)
        .order_by(DatabaseColumn.ordinal_position, DatabaseColumn.name)
    )
    columns = result.scalars().all()
    
    # Convert enum values inside session
    return [
        ColumnResponse(
            id=c.id,
            table_id=c.table_id,
            name=c.name,
            data_type=c.data_type,
            ordinal_position=c.ordinal_position,
            is_nullable=c.is_nullable,
            is_primary_key=c.is_primary_key,
            is_foreign_key=c.is_foreign_key,
            is_unique=c.is_unique,
            is_indexed=c.is_indexed,
            default_value=c.default_value,
            max_length=c.max_length,
            description=c.description,
        )
        for c in columns
    ]


# ── Relationships ─────────────────────────────────────────────────────────────

@router.get(
    "/tables/{table_id}/relationships",
    response_model=List[RelationshipResponse],
    summary="List FK relationships for a table",
)
async def list_relationships(table_id: int, db: AsyncSession = Depends(get_db)):
    table = await db.get(DatabaseTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table id={table_id} not found")

    result = await db.execute(
        select(DatabaseRelationship)
        .where(DatabaseRelationship.table_id == table_id)
    )
    relationships = result.scalars().all()
    
    # Convert inside session
    return [
        RelationshipResponse(
            id=r.id,
            table_id=r.table_id,
            column_name=r.column_name,
            referenced_table_name=r.referenced_table_name,
            referenced_column_name=r.referenced_column_name,
            referenced_schema=r.referenced_schema,
            constraint_name=r.constraint_name,
        )
        for r in relationships
    ]


# ── Sync Logs ─────────────────────────────────────────────────────────────────

@router.get(
    "/databases/{db_id}/sync-logs",
    response_model=List[SyncLogResponse],
    summary="Get sync history for a connection",
)
async def list_sync_logs(
    db_id: int,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(ConnectedDatabase, db_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection id={db_id} not found")

    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.connected_db_id == db_id)
        .order_by(SyncLog.started_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    # Convert inside session
    return [
        SyncLogResponse(
            id=log.id,
            connected_db_id=log.connected_db_id,
            status=log.status.value,
            started_at=log.started_at,
            completed_at=log.completed_at,
            duration_seconds=log.duration_seconds,
            schemas_synced=log.schemas_synced,
            tables_synced=log.tables_synced,
            columns_synced=log.columns_synced,
            relationships_synced=log.relationships_synced,
            error_message=log.error_message,
        )
        for log in logs
    ]


# ── Diagnostic endpoint ───────────────────────────────────────────────────────

@router.get(
    "/diagnose/{db_id}",
    summary="Diagnostic: Check what data exists for a connection",
)
async def diagnose_connection(db_id: int, db: AsyncSession = Depends(get_db)):
    """
    Debug endpoint to understand why tables aren't pulling.
    Returns: schemas count, tables count, columns count, last sync status
    """
    conn = await db.get(ConnectedDatabase, db_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection id={db_id} not found")

    # Count schemas
    result = await db.execute(
        select(DatabaseSchema).where(DatabaseSchema.connected_db_id == db_id)
    )
    schemas = result.scalars().all()
    schema_count = len(schemas)

    # Count tables and columns per schema
    tables_count = 0
    columns_count = 0
    for schema in schemas:
        result = await db.execute(
            select(DatabaseTable).where(DatabaseTable.schema_id == schema.id)
        )
        tables = result.scalars().all()
        tables_count += len(tables)
        for table in tables:
            result = await db.execute(
                select(DatabaseColumn).where(DatabaseColumn.table_id == table.id)
            )
            columns = result.scalars().all()
            columns_count += len(columns)

    # Get last sync
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.connected_db_id == db_id)
        .order_by(SyncLog.started_at.desc())
        .limit(1)
    )
    last_sync = result.scalars().first()

    return {
        "database_id": db_id,
        "database_name": conn.name,
        "status": conn.status.value,
        "schemas_count": schema_count,
        "tables_count": tables_count,
        "columns_count": columns_count,
        "last_sync": {
            "status": last_sync.status.value if last_sync else None,
            "completed_at": last_sync.completed_at if last_sync else None,
            "tables_synced": last_sync.tables_synced if last_sync else 0,
            "error": last_sync.error_message if last_sync else None,
        } if last_sync else None,
        "recommendation": (
            "Run 'Resync' from Connected Sources page to sync schema"
            if schema_count == 0
            else "Sync completed successfully" if tables_count > 0
            else "Sync completed but no tables found - check database"
        ),
    }
