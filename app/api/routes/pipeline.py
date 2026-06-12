"""
Pipeline operations APIs.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.pipeline_job import JobStatus, PipelineJob
from app.schemas.api_schemas import PipelineJobResponse, PipelineRunResponse
from app.schemas.stage_contracts import StageGraphResponse
from app.db.session import db_session
from app.services.pipeline_service import PipelineService
from app.services.database_pipeline_orchestrator import DatabasePipelineOrchestrator

router = APIRouter(prefix="/pipeline", tags=["Operations"])
logger = logging.getLogger(__name__)


def _to_job_response(job: PipelineJob) -> PipelineJobResponse:
    return PipelineJobResponse(
        id=job.id,
        job_type=job.job_type.value,
        database_id=job.database_id,
        parent_job_id=getattr(job, "parent_job_id", None),
        entity_table_id=getattr(job, "entity_table_id", None),
        entity_name=getattr(job, "entity_name", None),
        status=job.status.value,
        progress_percentage=job.progress_percentage,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failure_reason=job.failure_reason,
        triggered_by=job.triggered_by,
    )


@router.post(
    "/run/{db_id}",
    response_model=PipelineRunResponse,
    summary="Queue a full semantic pipeline run for a database",
)
async def run_pipeline(
    db_id: int,
    triggered_by: Optional[str] = Query(default="ui"),
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    service = PipelineService(db)
    try:
        result = await service.create_pipeline_run(db_id, triggered_by=triggered_by)
        return PipelineRunResponse(
            database_id=result.database_id,
            created_job_ids=result.created_job_ids,
            message=result.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Pipeline run failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue pipeline run",
        )


@router.get(
    "/jobs",
    response_model=list[PipelineJobResponse],
    summary="List pipeline jobs",
)
async def list_pipeline_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[PipelineJobResponse]:
    service = PipelineService(db)
    status_value: Optional[JobStatus] = None
    if status_filter:
        try:
            status_value = JobStatus(status_filter.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status {status_filter!r}",
            )

    jobs = await service.list_jobs(limit=limit, status=status_value)
    return [_to_job_response(job) for job in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=PipelineJobResponse,
    summary="Get a pipeline job by id",
)
async def get_pipeline_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> PipelineJobResponse:
    service = PipelineService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pipeline job {job_id} not found")
    return _to_job_response(job)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=PipelineJobResponse,
    summary="Retry a failed/cancelled pipeline job",
)
async def retry_pipeline_job(
    job_id: int,
    triggered_by: Optional[str] = Query(default="ui"),
    db: AsyncSession = Depends(get_db),
) -> PipelineJobResponse:
    service = PipelineService(db)
    try:
        job = await service.retry_job(job_id, triggered_by=triggered_by)
        return _to_job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Pipeline retry failed for job_id=%s: %s", job_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry pipeline job",
        )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=PipelineJobResponse,
    summary="Cancel a running/queued pipeline job",
)
async def cancel_pipeline_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> PipelineJobResponse:
    service = PipelineService(db)
    try:
        job = await service.cancel_job(job_id)
        return _to_job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Pipeline cancel failed for job_id=%s: %s", job_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel pipeline job",
        )


@router.post(
    "/generate-ai-context/{db_id}",
    summary="Database-level AI context generation (entity-level processing)",
)
async def generate_ai_context(
    db_id: int,
    background_tasks: BackgroundTasks,
    triggered_by: Optional[str] = Query(default="ui"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    orchestrator = DatabasePipelineOrchestrator(db)
    try:
        result = await orchestrator.start_run(db_id, triggered_by=triggered_by or "ui")

        async def _runner(parent_job_id: int) -> None:
            async with db_session() as session:
                await DatabasePipelineOrchestrator(session).execute_run(parent_job_id)

        background_tasks.add_task(_runner, result.parent_job_id)

        return {
            "database_id": db_id,
            "parent_job_id": result.parent_job_id,
            "entity_count": result.entity_count,
            "message": result.message,
            "status": "QUEUED",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/stage-graph/{db_id}",
    response_model=StageGraphResponse,
    summary="Get the internal stage graph and current stage statuses",
)
async def stage_graph(
    db_id: int,
    parent_job_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> StageGraphResponse:
    orchestrator = DatabasePipelineOrchestrator(db)
    try:
        payload = await orchestrator.get_stage_graph(db_id, parent_job_id=parent_job_id)
        return StageGraphResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Stage graph lookup failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load stage graph",
        )
