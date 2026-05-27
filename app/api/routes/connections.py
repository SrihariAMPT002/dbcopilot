"""
/connections  — test, register, sync, and remove database connections.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.api_schemas import (
    ConnectionDetail,
    ConnectionRequest,
    ConnectionSummary,
    SyncResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    APIResponse,
)
from app.services.connection_service import ConnectionService
from app.services.sync_service import SyncService

router = APIRouter(prefix="/connections", tags=["Connections"])
logger = logging.getLogger(__name__)


# ── POST /connections/test ────────────────────────────────────────────────────

@router.post(
    "/test",
    response_model=TestConnectionResponse,
    summary="Test database credentials without storing them",
)
async def test_connection(
    req: TestConnectionRequest,
    db: AsyncSession = Depends(get_db),
) -> TestConnectionResponse:
    """
    Validate credentials by opening a live connection and pinging the server.
    Nothing is persisted.
    """
    svc = ConnectionService(db)
    return await svc.test_connection(req)


# ── POST /connections ─────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ConnectionSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new database connection",
)
async def create_connection(
    req: ConnectionRequest,
    db: AsyncSession = Depends(get_db),
) -> ConnectionSummary:
    """
    Persist a new database connection.
    Password is encrypted at rest. Does NOT sync schema automatically — call
    POST /connections/{db_id}/sync after registering.
    """
    svc = ConnectionService(db)
    try:
        conn = await svc.create_connection(req)
        # Convert to DTO inside session
        return svc.to_summary(conn, schema_count=0, table_count=0)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ── GET /connections ──────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=List[ConnectionSummary],
    summary="List all registered connections",
)
async def list_connections(
    db: AsyncSession = Depends(get_db),
) -> List[ConnectionSummary]:
    svc = ConnectionService(db)
    # Service now returns List[ConnectionSummary], not raw ORM objects
    return await svc.list_connections()


# ── GET /connections/{db_id} ──────────────────────────────────────────────────

@router.get(
    "/{db_id}",
    response_model=ConnectionSummary,
    summary="Get a single connection",
)
async def get_connection(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> ConnectionSummary:
    svc = ConnectionService(db)
    conn = await svc.get_connection(db_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection id={db_id} not found")
    return conn


# ── POST /connections/{db_id}/sync ────────────────────────────────────────────

@router.post(
    "/{db_id}/sync",
    response_model=SyncResponse,
    summary="Sync schema metadata from a connected database",
)
async def sync_schema(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """
    Introspect the external database and persist schema metadata.
    Overwrites existing metadata for this connection.
    """
    sync_svc = SyncService(db)
    result = await sync_svc.sync(db_id)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.message,
        )
    return result


# ── DELETE /connections/{db_id} ───────────────────────────────────────────────

@router.delete(
    "/{db_id}",
    response_model=APIResponse,
    summary="Remove a connection and all its metadata",
)
async def delete_connection(
    db_id: int,
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    svc = ConnectionService(db)
    deleted = await svc.delete_connection(db_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Connection id={db_id} not found")
    return APIResponse(success=True, message=f"Connection id={db_id} deleted successfully")
