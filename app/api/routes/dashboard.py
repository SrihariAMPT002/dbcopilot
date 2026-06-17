"""Dashboard summary APIs."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
    GovernancePackage,
    RelationshipPackage,
    SemanticPackage,
    SchemaEmbedding,
)
from app.models.retrieval_evaluation import RetrievalEvaluation
from app.models.semantic_cache import SemanticCache
from app.models.prompt_package import PromptPackage
from app.models.prompt_embedding import PromptEmbedding
from app.models.retrieval_log import RetrievalLog
from app.models.pipeline_job import JobStatus, JobType, PipelineJob
from app.models.readiness_snapshot import ReadinessSnapshot
from app.services.cache_service import cache_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardSummaryResponse(BaseModel):
    database_id: int | None = None
    database_name: str | None = None
    cache_status: str = "live"
    total_databases: int = 0
    schemas: int = 0
    tables: int = 0
    columns: int = 0
    relationships: int = 0
    governance_coverage: float = 0.0
    semantic_coverage: float = 0.0
    relationship_coverage: float = 0.0
    kpi_count: int = 0
    embeddings_ready: int = 0
    embeddings_total: int = 0
    readiness_score: int = 0
    active_jobs: int = 0
    last_sync_at: datetime | None = None
    failed_jobs: int = 0
    completed_jobs_24h: int = 0
    failed_jobs_24h: int = 0
    prompt_packages: int = 0
    prompt_embeddings: int = 0
    latest_prompt_at: datetime | None = None
    semantic_cache_entries: int = 0
    retrieval_evaluations: int = 0
    retrieval_logs: int = 0


@router.get("", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    database_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    cache_key = f"dashboard:{database_id or 'latest'}"
    cached = await cache_service.get(cache_key)
    if cached:
        payload = DashboardSummaryResponse.model_validate(json.loads(cached))
        payload.cache_status = "cache"
        return payload
    selected_db_id = database_id
    selected_db_name = None
    if selected_db_id is None:
        result = await db.execute(select(ConnectedDatabase).order_by(ConnectedDatabase.created_at.desc()))
        latest = result.scalars().first()
        if latest is not None:
            selected_db_id = latest.id
            selected_db_name = latest.name
    else:
        row = await db.get(ConnectedDatabase, selected_db_id)
        if row is not None:
            selected_db_name = row.name

    total_databases = await db.scalar(select(func.count(ConnectedDatabase.id))) or 0

    if selected_db_id is None:
        return DashboardSummaryResponse(total_databases=int(total_databases))

    schema_count = int(
        await db.scalar(select(func.count(DatabaseSchema.id)).where(DatabaseSchema.connected_db_id == selected_db_id)) or 0
    )
    table_count = int(
        await db.scalar(
            select(func.count(DatabaseTable.id))
            .select_from(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == selected_db_id)
        )
        or 0
    )
    column_count = int(
        await db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == selected_db_id)
        )
        or 0
    )
    relationship_count = int(
        await db.scalar(
            select(func.count())
            .select_from(RelationshipPackage)
            .where(RelationshipPackage.database_id == selected_db_id)
        )
        or 0
    )
    governance_total = int(
        await db.scalar(select(func.count(GovernancePackage.id)).where(GovernancePackage.database_id == selected_db_id)) or 0
    )
    semantic_total = int(
        await db.scalar(select(func.count(SemanticPackage.id)).where(SemanticPackage.database_id == selected_db_id)) or 0
    )
    relationship_total = int(
        await db.scalar(select(func.count(RelationshipPackage.id)).where(RelationshipPackage.database_id == selected_db_id)) or 0
    )
    kpi_count = int(
        await db.scalar(
            select(func.count(PipelineJob.id)).where(
                PipelineJob.database_id == selected_db_id,
                PipelineJob.job_type == JobType.kpi,
            )
        )
        or 0
    )
    embeddings_total = int(
        await db.scalar(select(func.count(SchemaEmbedding.id)).select_from(SchemaEmbedding).join(DatabaseTable).join(DatabaseSchema).where(DatabaseSchema.connected_db_id == selected_db_id)) or 0
    )
    embeddings_ready = int(
        await db.scalar(
            select(func.count(SchemaEmbedding.id))
            .select_from(SchemaEmbedding)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == selected_db_id, SchemaEmbedding.embedding_status == "completed")
        )
        or 0
    )
    readiness_row = await db.execute(
        select(ReadinessSnapshot)
        .where(ReadinessSnapshot.database_id == selected_db_id)
        .order_by(ReadinessSnapshot.generated_at.desc())
        .limit(1)
    )
    latest_readiness = readiness_row.scalars().first()
    active_jobs = int(
        await db.scalar(
            select(func.count(PipelineJob.id))
            .where(PipelineJob.database_id == selected_db_id, PipelineJob.status.in_([JobStatus.queued, JobStatus.running]))
        )
        or 0
    )
    failed_jobs = int(
        await db.scalar(select(func.count(PipelineJob.id)).where(PipelineJob.database_id == selected_db_id, PipelineJob.status == JobStatus.failed)) or 0
    )
    completed_jobs_24h = int(
        await db.scalar(
            select(func.count(PipelineJob.id))
            .where(PipelineJob.database_id == selected_db_id, PipelineJob.status == JobStatus.completed)
        )
        or 0
    )
    failed_jobs_24h = failed_jobs
    prompt_packages = int(
        await db.scalar(select(func.count(PromptPackage.id)).where(PromptPackage.database_id == selected_db_id)) or 0
    )
    prompt_embeddings = int(
        await db.scalar(
            select(func.count(PromptEmbedding.id))
            .select_from(PromptEmbedding)
            .join(PromptPackage)
            .where(PromptPackage.database_id == selected_db_id)
        )
        or 0
    )
    latest_prompt_row = await db.execute(
        select(PromptPackage.created_at)
        .where(PromptPackage.database_id == selected_db_id)
        .order_by(PromptPackage.created_at.desc())
        .limit(1)
    )
    latest_prompt_at = latest_prompt_row.scalars().first()
    semantic_cache_entries = int(
        await db.scalar(select(func.count(SemanticCache.id)).where(SemanticCache.database_id == selected_db_id)) or 0
    )
    retrieval_evaluations = int(
        await db.scalar(select(func.count(RetrievalEvaluation.id)).where(RetrievalEvaluation.database_id == selected_db_id)) or 0
    )
    retrieval_logs = int(
        await db.scalar(select(func.count(RetrievalLog.id)).where(RetrievalLog.database_id == selected_db_id)) or 0
    )

    readiness_score = int(getattr(latest_readiness, "overall_score", 0) or 0)
    last_sync_at = None
    if selected_db_id is not None:
        conn = await db.get(ConnectedDatabase, selected_db_id)
        last_sync_at = getattr(conn, "last_sync_at", None)

    payload = DashboardSummaryResponse(
        database_id=selected_db_id,
        database_name=selected_db_name,
        cache_status="live",
        total_databases=int(total_databases),
        schemas=schema_count,
        tables=table_count,
        columns=column_count,
        relationships=relationship_count,
        governance_coverage=(governance_total / max(1, table_count)) * 100.0,
        semantic_coverage=(semantic_total / max(1, table_count)) * 100.0,
        relationship_coverage=(relationship_total / max(1, table_count)) * 100.0,
        kpi_count=kpi_count,
        embeddings_ready=embeddings_ready,
        embeddings_total=embeddings_total,
        readiness_score=readiness_score,
        active_jobs=active_jobs,
        last_sync_at=last_sync_at,
        failed_jobs=failed_jobs,
        completed_jobs_24h=completed_jobs_24h,
        failed_jobs_24h=failed_jobs_24h,
        prompt_packages=prompt_packages,
        prompt_embeddings=prompt_embeddings,
        latest_prompt_at=latest_prompt_at,
        semantic_cache_entries=semantic_cache_entries,
        retrieval_evaluations=retrieval_evaluations,
        retrieval_logs=retrieval_logs,
    )
    await cache_service.set(cache_key, payload.model_dump_json(), ttl_seconds=300)
    return payload
