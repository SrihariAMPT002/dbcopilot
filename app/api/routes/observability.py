"""Unified AI observability APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.metadata import ConnectedDatabase, DatabaseLifecycleEvent
from app.models.pipeline_execution import PipelineExecution, StageExecution
from app.models.prompt_observability_log import PromptObservabilityLog
from app.models.prompt_package import PromptPackage
from app.models.prompt_version import PromptVersion
from app.schemas.api_schemas import ExecutionTraceResponse

router = APIRouter(prefix="/observability", tags=["Observability"])


class ObservabilityTraceItem(BaseModel):
    source_type: str
    trace_id: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    database_id: Optional[int] = None
    module: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: Optional[str] = None
    execution_status: Optional[str] = None
    estimated_cost_usd: float = 0.0
    created_at: Optional[datetime] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ObservabilityTraceListResponse(BaseModel):
    database_id: Optional[int] = None
    trace_id: Optional[str] = None
    traces: list[ObservabilityTraceItem] = Field(default_factory=list)


class ObservabilityTraceDetailResponse(BaseModel):
    trace_id: str
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    deployment: Optional[str] = None
    module: Optional[str] = None
    artifact_type: Optional[str] = None
    database_id: Optional[int] = None
    latency_ms: float = 0.0
    finish_reason: Optional[str] = None
    execution_status: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: float = 0.0
    prompt_versions: list[dict[str, Any]] = Field(default_factory=list)
    pipeline_executions: list[dict[str, Any]] = Field(default_factory=list)
    stage_executions: list[dict[str, Any]] = Field(default_factory=list)
    prompt_observability: list[dict[str, Any]] = Field(default_factory=list)
    linked_job: Optional[dict[str, Any]] = None
    linked_pipeline_execution: Optional[dict[str, Any]] = None
    linked_stage_executions: list[dict[str, Any]] = Field(default_factory=list)
    linked_prompt_versions: list[dict[str, Any]] = Field(default_factory=list)
    execution_trace: Optional[ExecutionTraceResponse] = None


class LifecycleEventItem(BaseModel):
    id: int
    connected_db_id: int
    event_type: str
    actor: Optional[str] = None
    reason: Optional[str] = None
    trace_id: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: Optional[datetime] = None


class LifecycleEventResponse(BaseModel):
    database_id: int
    events: list[LifecycleEventItem] = Field(default_factory=list)


def _estimate_cost(prompt_tokens: int, completion_tokens: int, reasoning_tokens: int) -> float:
    total = prompt_tokens + completion_tokens + reasoning_tokens
    return round(total * 0.0000015, 6)


def _normalize_trace_details(payload: dict[str, Any] | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    fallback = fallback or {}
    return {
        "token_usage_json": data.get("token_usage_json", fallback.get("token_usage_json", "{}")),
        "pipeline_context_json": data.get("pipeline_context_json", fallback.get("pipeline_context_json")),
        "context_source": data.get("context_source", fallback.get("context_source")),
        "used_context": data.get("used_context", fallback.get("used_context")),
        "fallback_reason": data.get("fallback_reason", fallback.get("fallback_reason")),
        "estimated_input_tokens": int(data.get("estimated_input_tokens", fallback.get("estimated_input_tokens", 0)) or 0),
        "actual_input_tokens": int(data.get("actual_input_tokens", fallback.get("actual_input_tokens", 0)) or 0),
        "estimated_output_tokens": int(data.get("estimated_output_tokens", fallback.get("estimated_output_tokens", 0)) or 0),
        "actual_output_tokens": int(data.get("actual_output_tokens", fallback.get("actual_output_tokens", 0)) or 0),
        "prompt_size_bytes": int(data.get("prompt_size_bytes", fallback.get("prompt_size_bytes", 0)) or 0),
        "completion_truncated": bool(data.get("completion_truncated", fallback.get("completion_truncated", False))),
        "error_message": data.get("error_message", fallback.get("error_message")),
        "blocked_by_stage": data.get("blocked_by_stage", fallback.get("blocked_by_stage")),
        "prompt_version": data.get("prompt_version", fallback.get("prompt_version")),
        "model_name": data.get("model_name", fallback.get("model_name")),
        "trace_id": data.get("trace_id", fallback.get("trace_id")),
        "request_id": data.get("request_id", fallback.get("request_id")),
    }


def _execution_trace_from_observability(
    *,
    trace_id: str,
    database_id: int,
    prompt_id: Optional[str],
    prompt_version: Optional[str],
    model_name: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    latency_ms: float,
    finish_reason: Optional[str],
    execution_status: Optional[str],
    started_at: Optional[datetime],
    completed_at: Optional[datetime],
    error_message: Optional[str] = None,
) -> ExecutionTraceResponse:
    total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
    return ExecutionTraceResponse(
        trace_id=trace_id,
        request_id=trace_id,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        database_id=database_id,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        execution_status=execution_status,
        started_at=started_at,
        completed_at=completed_at,
        error_message=error_message,
    )


async def _load_trace_list(
    database_id: int,
    *,
    module: str | None = None,
    model_name: str | None = None,
    trace_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession,
) -> ObservabilityTraceListResponse:
    db_row = await db.get(ConnectedDatabase, database_id)
    if db_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {database_id} not found")

    traces: list[ObservabilityTraceItem] = []

    prompt_stmt = (
        select(PromptObservabilityLog, PromptPackage)
        .join(PromptPackage, PromptPackage.id == PromptObservabilityLog.prompt_package_id)
        .where(PromptPackage.database_id == database_id)
    )
    if model_name:
        prompt_stmt = prompt_stmt.where(PromptObservabilityLog.model_name == model_name)
    if trace_id:
        prompt_stmt = prompt_stmt.where(PromptObservabilityLog.trace_id == trace_id)
    if from_date:
        prompt_stmt = prompt_stmt.where(func.date(PromptObservabilityLog.created_at) >= from_date)
    if to_date:
        prompt_stmt = prompt_stmt.where(func.date(PromptObservabilityLog.created_at) <= to_date)
    prompt_rows = (await db.execute(prompt_stmt.order_by(PromptObservabilityLog.created_at.desc()).limit(500))).all()
    for log, package in prompt_rows:
        details = _normalize_trace_details(
            {
                "prompt_version": getattr(package, "prompt_version", None),
                "model_name": getattr(log, "model_name", None),
                "trace_id": getattr(log, "trace_id", None),
            }
        )
        traces.append(
            ObservabilityTraceItem(
                source_type="prompt",
                trace_id=details.get("trace_id"),
                prompt_id=getattr(package, "template_id", None),
                prompt_version=details.get("prompt_version"),
                model_name=details.get("model_name"),
                database_id=database_id,
                module="prompt_studio",
                prompt_tokens=log.prompt_tokens or 0,
                completion_tokens=log.completion_tokens or 0,
                reasoning_tokens=log.reasoning_tokens or 0,
                latency_ms=log.latency_ms or 0.0,
                finish_reason=log.finish_reason,
                execution_status=log.execution_status,
                estimated_cost_usd=_estimate_cost(log.prompt_tokens or 0, log.completion_tokens or 0, log.reasoning_tokens or 0),
                created_at=log.created_at,
                details=_normalize_trace_details(
                    {"error_message": getattr(log, "failure_reason", getattr(log, "raw_failure_reason", None))},
                    fallback={"prompt_package_id": log.prompt_package_id},
                ),
            )
        )

    pipe_stmt = select(PipelineExecution).where(PipelineExecution.database_id == database_id)
    if model_name:
        pipe_stmt = pipe_stmt.where(PipelineExecution.model_name == model_name)
    if trace_id:
        pipe_stmt = pipe_stmt.where(PipelineExecution.trace_id == trace_id)
    if from_date:
        pipe_stmt = pipe_stmt.where(func.date(PipelineExecution.start_time) >= from_date)
    if to_date:
        pipe_stmt = pipe_stmt.where(func.date(PipelineExecution.start_time) <= to_date)
    pipe_rows = (await db.execute(pipe_stmt.order_by(PipelineExecution.start_time.desc()).limit(200))).scalars().all()
    for row in pipe_rows:
        details = _normalize_trace_details(
            {
                "token_usage_json": getattr(row, "token_usage_json", "{}"),
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "estimated_input_tokens": getattr(row, "estimated_input_tokens", 0),
                "actual_input_tokens": getattr(row, "actual_input_tokens", 0),
                "estimated_output_tokens": getattr(row, "estimated_output_tokens", 0),
                "actual_output_tokens": getattr(row, "actual_output_tokens", 0),
                "prompt_size_bytes": getattr(row, "prompt_size_bytes", 0),
                "completion_truncated": getattr(row, "completion_truncated", False),
                "error_message": getattr(row, "error_message", None),
                "trace_id": getattr(row, "trace_id", None),
                "model_name": getattr(row, "model_name", None),
            }
        )
        traces.append(
            ObservabilityTraceItem(
                source_type="pipeline",
                trace_id=details.get("trace_id"),
                prompt_id=getattr(row, "triggered_by", None),
                model_name=details.get("model_name"),
                database_id=database_id,
                module="pipeline",
                latency_ms=row.duration_seconds * 1000 if getattr(row, "duration_seconds", None) else 0.0,
                finish_reason=getattr(row, "status", None),
                execution_status=getattr(row, "status", None),
                created_at=row.start_time,
                details=details,
            )
        )

    stage_stmt = select(StageExecution).where(StageExecution.database_id == database_id)
    if model_name:
        stage_stmt = stage_stmt.where(StageExecution.model_name == model_name)
    if trace_id:
        stage_stmt = stage_stmt.where(StageExecution.trace_id == trace_id)
    if from_date:
        stage_stmt = stage_stmt.where(func.date(StageExecution.start_time) >= from_date)
    if to_date:
        stage_stmt = stage_stmt.where(func.date(StageExecution.start_time) <= to_date)
    stage_rows = (await db.execute(stage_stmt.order_by(StageExecution.start_time.desc()).limit(300))).scalars().all()
    for row in stage_rows:
        details = _normalize_trace_details(
            {
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "estimated_input_tokens": getattr(row, "estimated_input_tokens", 0),
                "actual_input_tokens": getattr(row, "actual_input_tokens", 0),
                "estimated_output_tokens": getattr(row, "estimated_output_tokens", 0),
                "actual_output_tokens": getattr(row, "actual_output_tokens", 0),
                "prompt_size_bytes": getattr(row, "prompt_size_bytes", 0),
                "completion_truncated": getattr(row, "completion_truncated", False),
                "error_message": getattr(row, "error_message", None),
                "blocked_by_stage": getattr(row, "blocked_by_stage", None),
                "trace_id": getattr(row, "trace_id", None),
                "model_name": getattr(row, "model_name", None),
            }
        )
        traces.append(
            ObservabilityTraceItem(
                source_type="stage",
                trace_id=details.get("trace_id"),
                prompt_id=getattr(row, "stage_name", None),
                model_name=details.get("model_name"),
                database_id=database_id,
                module=module or "pipeline",
                latency_ms=row.duration_seconds * 1000 if getattr(row, "duration_seconds", None) else 0.0,
                finish_reason=getattr(row, "status", None),
                execution_status=getattr(row, "status", None),
                created_at=row.start_time,
                details={**details, "pipeline_execution_id": getattr(row, "pipeline_execution_id", None), "execution_order": getattr(row, "execution_order", None)},
            )
        )

    traces.sort(key=lambda item: item.created_at or datetime.min, reverse=True)
    return ObservabilityTraceListResponse(database_id=database_id, trace_id=trace_id, traces=traces[:500])


@router.get("/{database_id}", response_model=ObservabilityTraceListResponse, summary="List unified observability traces")
async def list_observability_traces(
    database_id: int,
    module: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ObservabilityTraceListResponse:
    return await _load_trace_list(
        database_id,
        module=module,
        model_name=model_name,
        trace_id=trace_id,
        from_date=from_date,
        to_date=to_date,
        db=db,
    )


@router.get("/traces/{database_id}", response_model=ObservabilityTraceListResponse)
async def list_observability_traces_alias(
    database_id: int,
    module: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ObservabilityTraceListResponse:
    return await _load_trace_list(
        database_id,
        module=module,
        model_name=model_name,
        trace_id=trace_id,
        from_date=from_date,
        to_date=to_date,
        db=db,
    )


async def _get_trace_detail(database_id: int, trace_id: str, db: AsyncSession) -> ObservabilityTraceDetailResponse:
    db_row = await db.get(ConnectedDatabase, database_id)
    if db_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {database_id} not found")

    prompt_row = await db.execute(
        select(PromptObservabilityLog, PromptPackage)
        .join(PromptPackage, PromptPackage.id == PromptObservabilityLog.prompt_package_id)
        .where(PromptPackage.database_id == database_id, PromptObservabilityLog.trace_id == trace_id)
        .order_by(PromptObservabilityLog.created_at.desc())
    )
    prompt_records = prompt_row.all()
    stage_rows = (
        await db.execute(
            select(StageExecution).where(StageExecution.database_id == database_id, StageExecution.trace_id == trace_id)
        )
    ).scalars().all()
    pipe_rows = (
        await db.execute(
            select(PipelineExecution).where(PipelineExecution.database_id == database_id, PipelineExecution.trace_id == trace_id)
        )
    ).scalars().all()
    version_rows = (
        await db.execute(
            select(PromptVersion, PromptPackage)
            .join(PromptPackage, PromptPackage.id == PromptVersion.prompt_package_id)
            .where(PromptPackage.database_id == database_id)
            .order_by(PromptVersion.created_at.desc())
        )
    ).all()

    prompt_detail = prompt_records[0][0] if prompt_records else None
    package_detail = prompt_records[0][1] if prompt_records else None
    prompt_tokens = getattr(prompt_detail, "prompt_tokens", 0) if prompt_detail else 0
    completion_tokens = getattr(prompt_detail, "completion_tokens", 0) if prompt_detail else 0
    reasoning_tokens = getattr(prompt_detail, "reasoning_tokens", 0) if prompt_detail else 0
    linked_pipeline = pipe_rows[0] if pipe_rows else None
    linked_stage = stage_rows[0] if stage_rows else None
    prompt_meta = _normalize_trace_details(
        {
            "prompt_version": getattr(package_detail, "prompt_version", None),
            "model_name": getattr(prompt_detail, "model_name", None) if prompt_detail else None,
            "trace_id": trace_id,
        }
    )
    return ObservabilityTraceDetailResponse(
        trace_id=trace_id,
        prompt_id=getattr(package_detail, "template_id", None) if package_detail else None,
        prompt_version=prompt_meta["prompt_version"],
        model_name=prompt_meta["model_name"],
        deployment=prompt_meta["model_name"],
        module="prompt_studio",
        artifact_type=getattr(package_detail, "artifact_type", None) if package_detail else None,
        database_id=database_id,
        latency_ms=getattr(prompt_detail, "latency_ms", 0.0) if prompt_detail else 0.0,
        finish_reason=getattr(prompt_detail, "finish_reason", None) if prompt_detail else None,
        execution_status=getattr(prompt_detail, "execution_status", None) if prompt_detail else None,
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
        reasoning_tokens=reasoning_tokens or 0,
        estimated_cost_usd=_estimate_cost(prompt_tokens or 0, completion_tokens or 0, reasoning_tokens or 0),
        prompt_versions=[
            {
                "id": version.id,
                "prompt_package_id": version.prompt_package_id,
                "version": version.version,
                "generated_prompt": version.generated_prompt,
                "model_name": getattr(version, "model_name", None),
                "template_id": getattr(version, "template_id", None),
                "trace_id": getattr(version, "trace_id", None),
                "created_at": version.created_at,
            }
            for version, _package in version_rows
        ],
        pipeline_executions=[
            {
                "id": row.id,
                "status": getattr(row, "status", None),
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration_seconds": row.duration_seconds,
                "model_name": getattr(row, "model_name", None),
                "trace_id": getattr(row, "trace_id", None),
                "estimated_input_tokens": getattr(row, "estimated_input_tokens", 0),
                "actual_input_tokens": getattr(row, "actual_input_tokens", 0),
                "estimated_output_tokens": getattr(row, "estimated_output_tokens", 0),
                "actual_output_tokens": getattr(row, "actual_output_tokens", 0),
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "prompt_size_bytes": getattr(row, "prompt_size_bytes", 0),
                "completion_truncated": getattr(row, "completion_truncated", False),
                "triggered_by": getattr(row, "triggered_by", None),
                "error_message": getattr(row, "error_message", None),
            }
            for row in pipe_rows
        ],
        stage_executions=[
            {
                "id": row.id,
                "stage_name": getattr(row, "stage_name", None),
                "status": getattr(row, "status", None),
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration_seconds": row.duration_seconds,
                "model_name": getattr(row, "model_name", None),
                "trace_id": getattr(row, "trace_id", None),
                "estimated_input_tokens": getattr(row, "estimated_input_tokens", 0),
                "actual_input_tokens": getattr(row, "actual_input_tokens", 0),
                "estimated_output_tokens": getattr(row, "estimated_output_tokens", 0),
                "actual_output_tokens": getattr(row, "actual_output_tokens", 0),
                "pipeline_context_json": getattr(row, "pipeline_context_json", None),
                "context_source": getattr(row, "context_source", None),
                "used_context": getattr(row, "used_context", None),
                "fallback_reason": getattr(row, "fallback_reason", None),
                "prompt_size_bytes": getattr(row, "prompt_size_bytes", 0),
                "completion_truncated": getattr(row, "completion_truncated", False),
                "execution_order": getattr(row, "execution_order", None),
                "error_message": getattr(row, "error_message", None),
                "blocked_by_stage": getattr(row, "blocked_by_stage", None),
            }
            for row in stage_rows
        ],
        prompt_observability=[
            {
                "id": row.id,
                "prompt_package_id": row.prompt_package_id,
                "trace_id": row.trace_id,
                "model_name": row.model_name,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "reasoning_tokens": row.reasoning_tokens,
                "estimated_input_tokens": row.estimated_input_tokens,
                "actual_input_tokens": row.actual_input_tokens,
                "estimated_output_tokens": row.estimated_output_tokens,
                "actual_output_tokens": row.actual_output_tokens,
                "prompt_size_bytes": row.prompt_size_bytes,
                "completion_truncated": row.completion_truncated,
                "latency_ms": row.latency_ms,
                "finish_reason": row.finish_reason,
                "execution_status": row.execution_status,
                "failure_reason": getattr(row, "failure_reason", getattr(row, "raw_failure_reason", None)),
                "created_at": row.created_at,
            }
            for row, _pkg in prompt_records
        ],
        linked_job={
            "job_id": getattr(linked_stage, "job_id", None) if linked_stage else None,
            "parent_job_id": getattr(linked_pipeline, "parent_job_id", None) if linked_pipeline else None,
            "trace_id": trace_id,
            "database_id": database_id,
        },
        linked_pipeline_execution=
            {
                "pipeline_execution_id": linked_pipeline.id,
                "trace_id": getattr(linked_pipeline, "trace_id", None),
                "database_id": database_id,
            }
            if linked_pipeline
            else None,
        linked_stage_executions=[
            {
                "stage_execution_id": row.id,
                "pipeline_execution_id": row.pipeline_execution_id,
                "trace_id": row.trace_id,
                "stage_name": row.stage_name,
                "database_id": database_id,
            }
            for row in stage_rows
        ],
        linked_prompt_versions=[
            {
                "prompt_version_id": version.id,
                "prompt_package_id": version.prompt_package_id,
                "trace_id": version.trace_id,
                "version": version.version,
            }
            for version, _package in version_rows[:5]
        ],
        execution_trace=_execution_trace_from_observability(
            trace_id=trace_id,
            database_id=database_id,
            prompt_id=getattr(package_detail, "template_id", None) if package_detail else None,
            prompt_version=prompt_meta["prompt_version"],
            model_name=prompt_meta["model_name"],
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            reasoning_tokens=reasoning_tokens or 0,
            latency_ms=getattr(prompt_detail, "latency_ms", 0.0) if prompt_detail else 0.0,
            finish_reason=getattr(prompt_detail, "finish_reason", None) if prompt_detail else None,
            execution_status=getattr(prompt_detail, "execution_status", None) if prompt_detail else None,
            started_at=getattr(prompt_detail, "created_at", None) if prompt_detail else None,
            completed_at=getattr(prompt_detail, "created_at", None) if prompt_detail else None,
            error_message=getattr(prompt_detail, "failure_reason", None) if prompt_detail else None,
        ),
    )


@router.get("/{database_id}/{trace_id}", response_model=ObservabilityTraceDetailResponse, summary="Get trace details")
async def get_trace_detail(database_id: int, trace_id: str, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceDetailResponse:
    return await _get_trace_detail(database_id, trace_id, db)


@router.get("/trace/{database_id}/{trace_id}", response_model=ObservabilityTraceDetailResponse, summary="Alias for trace details")
async def get_trace_detail_alias(database_id: int, trace_id: str, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceDetailResponse:
    return await _get_trace_detail(database_id, trace_id, db)


@router.get("/{database_id}/events", response_model=LifecycleEventResponse, summary="List database lifecycle events")
async def list_lifecycle_events(database_id: int, db: AsyncSession = Depends(get_db)) -> LifecycleEventResponse:
    db_row = await db.get(ConnectedDatabase, database_id)
    if db_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Database {database_id} not found")
    rows = (
        await db.execute(
            select(DatabaseLifecycleEvent)
            .where(DatabaseLifecycleEvent.connected_db_id == database_id)
            .order_by(DatabaseLifecycleEvent.created_at.desc())
        )
    ).scalars().all()
    return LifecycleEventResponse(
        database_id=database_id,
        events=[
            LifecycleEventItem(
                id=row.id,
                connected_db_id=row.connected_db_id,
                event_type=row.event_type,
                actor=row.actor,
                reason=row.reason,
                trace_id=row.trace_id,
                metadata_json=row.metadata_json,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.get("/pipeline/{database_id}", response_model=ObservabilityTraceListResponse, summary="Alias for pipeline-oriented trace list")
async def pipeline_observability(database_id: int, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceListResponse:
    return await _load_trace_list(database_id, db=db)


@router.get("/prompts/{database_id}", response_model=ObservabilityTraceListResponse, summary="Alias for prompt-oriented trace list")
async def prompt_observability(database_id: int, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceListResponse:
    return await _load_trace_list(database_id, module="prompt_studio", db=db)


@router.get("/tokens/{database_id}", response_model=ObservabilityTraceListResponse, summary="Alias for token analytics")
async def token_observability(database_id: int, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceListResponse:
    return await _load_trace_list(database_id, db=db)


@router.get("/costs/{database_id}", response_model=ObservabilityTraceListResponse, summary="Alias for cost analytics")
async def cost_observability(database_id: int, db: AsyncSession = Depends(get_db)) -> ObservabilityTraceListResponse:
    return await _load_trace_list(database_id, db=db)
