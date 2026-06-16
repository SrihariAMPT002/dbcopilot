"""
/connections  — test, register, sync, and remove database connections.
"""

import logging
import time
from typing import List

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.session import db_session
from app.models.pipeline_job import JobStatus, JobType
from app.schemas.api_schemas import (
    ConnectionLifecycleConfirmRequest,
    ConnectionLifecycleDeleteRequest,
    ConnectionLifecycleResponse,
    ConnectionRequest,
    ConnectionSummary,
    JobQueueResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.connection_service import ConnectionService
from app.services.sync_service import SyncService
from app.services.pipeline_service import PipelineService

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
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
) -> List[ConnectionSummary]:
    svc = ConnectionService(db)
    # Service now returns List[ConnectionSummary], not raw ORM objects
    return await svc.list_connections(include_archived=include_archived)


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
    response_model=JobQueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue schema sync for a connected database",
)
async def sync_schema(
    db_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JobQueueResponse:
    """
    Introspect the external database and persist schema metadata.
    Overwrites existing metadata for this connection.
    """
    pipeline = PipelineService(db)
    try:
        job = await pipeline.create_job(db_id, JobType.sync, triggered_by="api")

        async def _runner(job_id: int) -> None:
            async with db_session() as session:
                service = SyncService(session)
                job_service = PipelineService(session)
                try:
                    result = await service.sync(db_id)
                    if result.success:
                        await job_service.update_status(job_id, JobStatus.completed, progress_percentage=100)
                    else:
                        await job_service.update_status(job_id, JobStatus.failed, progress_percentage=0, failure_reason=result.message)
                except Exception as exc:
                    logger.exception("Background sync job failed for db_id=%s job_id=%s", db_id, job_id)
                    await job_service.update_status(job_id, JobStatus.failed, progress_percentage=0, failure_reason=str(exc))

        background_tasks.add_task(_runner, job.id)
        return JobQueueResponse(
            database_id=db_id,
            job_id=job.id,
            job_type=JobType.sync.value,
            status=job.status.value,
            message="Schema sync queued. Poll /pipeline/jobs/{job_id} for progress.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Sync queue failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to queue sync job")


# ── DELETE /connections/{db_id} ───────────────────────────────────────────────

@router.delete(
    "/{db_id}",
    response_model=APIResponse,
    summary="Remove a connection and all its metadata",
)
async def delete_connection(
    db_id: int,
    payload: ConnectionLifecycleDeleteRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConnectionLifecycleResponse:
    svc = ConnectionService(db)
    try:
        return await svc.delete_connection_hard(
            db_id,
            delete_metadata=payload.delete_metadata,
            delete_packages=payload.delete_packages,
            delete_embeddings=payload.delete_embeddings,
            delete_observability=payload.delete_observability,
            confirmation_text=payload.confirmation_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{db_id}/disconnect",
    response_model=ConnectionLifecycleResponse,
    summary="Disconnect a connection while preserving intelligence artifacts",
)
async def disconnect_connection(
    db_id: int,
    payload: ConnectionLifecycleConfirmRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConnectionLifecycleResponse:
    svc = ConnectionService(db)
    try:
        return await svc.disconnect_connection(db_id, confirmation_text=payload.confirmation_text, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{db_id}/reconnect",
    response_model=ConnectionLifecycleResponse,
    summary="Reconnect a disconnected or archived database",
)
async def reconnect_connection(
    db_id: int,
    payload: ConnectionLifecycleConfirmRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConnectionLifecycleResponse:
    svc = ConnectionService(db)
    try:
        return await svc.reconnect_connection(db_id, confirmation_text=payload.confirmation_text, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{db_id}/archive",
    response_model=ConnectionLifecycleResponse,
    summary="Archive a connection and preserve all intelligence artifacts",
)
async def archive_connection(
    db_id: int,
    payload: ConnectionLifecycleConfirmRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConnectionLifecycleResponse:
    svc = ConnectionService(db)
    try:
        return await svc.archive_connection(db_id, confirmation_text=payload.confirmation_text, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{db_id}/restore",
    response_model=ConnectionLifecycleResponse,
    summary="Restore an archived connection",
)
async def restore_connection(
    db_id: int,
    payload: ConnectionLifecycleConfirmRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConnectionLifecycleResponse:
    svc = ConnectionService(db)
    try:
        return await svc.restore_connection(db_id, confirmation_text=payload.confirmation_text, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
