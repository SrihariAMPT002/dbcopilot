"""
Pipeline operations APIs.
"""

from __future__ import annotations

import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.pipeline_job import JobStatus, PipelineJob
from app.models.pipeline_execution import PipelineExecution, StageExecution
from app.schemas.api_schemas import PipelineJobResponse, PipelineRunResponse
from app.schemas.stage_contracts import StageGraphResponse, StageProgressResponse
from app.db.session import db_session
from app.services.pipeline_service import PipelineService
from app.services.database_pipeline_orchestrator import DatabasePipelineOrchestrator
from app.services.cache_service import cache_service

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
        failure_reason=getattr(job, "failure_reason", None),
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


@router.get(
    "/stage-progress/{db_id}",
    response_model=StageProgressResponse,
    summary="Get canonical per-stage progress for a database",
)
async def stage_progress(
    db_id: int,
    parent_job_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> StageProgressResponse:
    orchestrator = DatabasePipelineOrchestrator(db)
    try:
        cache_key = f"pipeline:{db_id}:stage-progress:{parent_job_id or 'root'}"
        cached = await cache_service.get(cache_key)
        if cached:
            payload = StageProgressResponse.model_validate(json.loads(cached))
            payload.cache_status = "cache"
            return payload
        payload = await orchestrator.get_stage_progress(db_id, parent_job_id=parent_job_id)
        payload.cache_status = "live"
        await cache_service.set(cache_key, payload.model_dump_json())
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Stage progress lookup failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load stage progress",
        )


@router.get(
    "/executions/{db_id}",
    summary="List persisted pipeline executions for a database",
)
async def list_pipeline_executions(
    db_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cache_key = f"pipeline:{db_id}:executions:{limit}"
    cached = await cache_service.get(cache_key)
    if cached:
        return json.loads(cached)
    result = await db.execute(
        select(PipelineExecution)
        .where(PipelineExecution.database_id == db_id)
        .order_by(PipelineExecution.start_time.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    payload = {
        "database_id": db_id,
        "executions": [
            {
                "id": row.id,
                "database_id": row.database_id,
                "status": row.status,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration_seconds": row.duration_seconds,
                "trace_id": row.trace_id,
                "model_name": row.model_name,
                "token_usage_json": row.token_usage_json,
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "estimated_input_tokens": row.estimated_input_tokens,
                "actual_input_tokens": row.actual_input_tokens,
                "estimated_output_tokens": row.estimated_output_tokens,
                "actual_output_tokens": row.actual_output_tokens,
                "prompt_size_bytes": row.prompt_size_bytes,
                "completion_truncated": row.completion_truncated,
                "error_message": row.error_message,
                "triggered_by": row.triggered_by,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }
    await cache_service.set(cache_key, json.dumps(payload, default=str))
    return payload


@router.get(
    "/executions/{db_id}/stages",
    summary="List persisted stage executions for a database",
)
async def list_stage_executions(
    db_id: int,
    pipeline_execution_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cache_key = f"pipeline:{db_id}:stages:{pipeline_execution_id or 'all'}:{limit}"
    cached = await cache_service.get(cache_key)
    if cached:
        return json.loads(cached)
    stmt = select(StageExecution).where(StageExecution.database_id == db_id).order_by(StageExecution.start_time.desc()).limit(limit)
    if pipeline_execution_id is not None:
        stmt = stmt.where(StageExecution.pipeline_execution_id == pipeline_execution_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    payload = {
        "database_id": db_id,
        "pipeline_execution_id": pipeline_execution_id,
        "stage_executions": [
            {
                "id": row.id,
                "pipeline_execution_id": row.pipeline_execution_id,
                "database_id": row.database_id,
                "stage_name": row.stage_name,
                "status": row.status,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration_seconds": row.duration_seconds,
                "trace_id": row.trace_id,
                "model_name": row.model_name,
                "token_usage_json": row.token_usage_json,
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "estimated_input_tokens": row.estimated_input_tokens,
                "actual_input_tokens": row.actual_input_tokens,
                "estimated_output_tokens": row.estimated_output_tokens,
                "actual_output_tokens": row.actual_output_tokens,
                "prompt_size_bytes": row.prompt_size_bytes,
                "completion_truncated": row.completion_truncated,
                "error_message": row.error_message,
                "execution_order": row.execution_order,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }
    await cache_service.set(cache_key, json.dumps(payload, default=str))
    return payload
