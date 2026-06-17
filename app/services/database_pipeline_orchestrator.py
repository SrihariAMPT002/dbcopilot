"""
Database-level orchestration for AI context generation.

External UX: database-level "Generate AI Context".
Internal execution: entity-level processing with operational tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Any
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, DatabaseType
from app.models.pipeline_job import PipelineJob
from app.models.pipeline_job import JobStatus, JobType
from app.services.database_guard import ensure_connected
from app.schema_engine.embeddings import EmbeddingEngine
from app.schema_engine.enricher import SchemaEnricher
from app.services.artifact_service import ArtifactService
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.mongodb_service import MongoDBService
from app.services.pipeline_service import PipelineService
from app.services.readiness_service import ReadinessService
from app.services.prompt_studio_service import PromptStudioService
from app.schemas.stage_contracts import StageProgressItem, StageProgressResponse
from app.services.pipeline_context import (
    EmbeddingContext,
    GovernanceContext,
    IntelligenceContext,
    KPIContext,
    PromptContext,
    RelationshipContext,
    SemanticContext,
)
from app.core.structured_logging import error_message, stage_message, sync_message

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorRunResult:
    parent_job_id: int
    entity_count: int
    message: str


@dataclass
class StageGraphNode:
    stage: str
    job_type: JobType
    depends_on: list[str]
    stage_name: str


STAGE_GRAPH: list[StageGraphNode] = [
    StageGraphNode("metadata", JobType.sync, [], "Metadata"),
    StageGraphNode("governance", JobType.semantic, ["metadata"], "Governance"),
    StageGraphNode("semantics", JobType.semantic, ["governance"], "Semantics"),
    StageGraphNode("relationships", JobType.relationship_graph, ["governance", "semantics"], "Relationships"),
    StageGraphNode("kpi", JobType.kpi, ["governance", "semantics", "relationships"], "KPI"),
    StageGraphNode("prompt", JobType.prompt, ["kpi"], "Prompt"),
    StageGraphNode("embeddings", JobType.embeddings, ["prompt"], "Embeddings"),
    StageGraphNode("readiness", JobType.readiness, ["embeddings", "prompt"], "Readiness"),
]


class DatabasePipelineOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.pipeline = PipelineService(db)

    async def start_run(self, database_id: int, *, triggered_by: str = "ui") -> OrchestratorRunResult:
        database = await self._fetch_database(database_id)
        entities = await self._fetch_entities(database_id)

        parent = await self.pipeline.create_job(
            database_id=database_id,
            job_type=JobType.ai_context,
            triggered_by=triggered_by,
        )
        await self.pipeline.update_status(parent.id, JobStatus.queued, progress_percentage=0)

        # Create the stage graph as internal jobs.
        for node in STAGE_GRAPH:
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=node.job_type,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                stage_name=node.stage,
                depends_on=node.depends_on,
            )

        # Child semantic/embedding jobs remain entity-scoped, but are sequenced by the stage graph.
        for table in entities:
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=JobType.semantic,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                entity_table_id=table.id,
                entity_name=f"{table.schema.name}.{table.name}",
                stage_name="governance",
                depends_on=["semantics"],
            )
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=JobType.embeddings,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                entity_table_id=table.id,
                entity_name=f"{table.schema.name}.{table.name}",
                stage_name="embeddings",
                depends_on=["prompt"],
            )

        return OrchestratorRunResult(
            parent_job_id=parent.id,
            entity_count=len(entities),
            message=f"Queued AI context generation for {database.display_name or database.name} ({len(entities)} entities)",
        )

    async def execute_run(self, parent_job_id: int) -> None:
        parent = await self.pipeline.get_job(parent_job_id)
        if not parent:
            raise ValueError(f"Pipeline job {parent_job_id} not found")

        await self.pipeline.update_status(parent_job_id, JobStatus.running, progress_percentage=1)
        logger.info(sync_message("orchestrator run started", db_id=database_id, parent_job_id=parent_job_id))

        database_id = parent.database_id
        database = await self._fetch_database(database_id)

        # For MongoDB: ensure NoSQL registry exists (schema inference is a separate button per collection today).
        if database.db_type == DatabaseType.mongodb:
            try:
                await MongoDBService(self.db).ensure_collection_registry(database_id)
            except Exception as exc:
                logger.warning(error_message("mongo registry refresh failed", db_id=database_id, reason=exc))

        entities = await self._fetch_entities(database_id)
        total_units = max(1, len(entities) * 2 + len(STAGE_GRAPH))
        completed_units = 0

        # Run stage graph in order; each stage can resume independently.
        enricher = SchemaEnricher(self.db)
        embedder = EmbeddingEngine(self.db)
        context = IntelligenceContext()
        failed_stage: str | None = None

        for node in STAGE_GRAPH:
            if (await self.pipeline.get_job(parent_job_id)).status == JobStatus.cancelled:
                await self.pipeline.update_status(parent_job_id, JobStatus.cancelled)
                return

            job_id = await self._stage_job_id(parent_job_id, node.stage)
            if job_id is None:
                completed_units += 1
                continue

            if failed_stage is not None and node.stage not in {"metadata"}:
                await self.pipeline.update_status(
                    job_id,
                    JobStatus.failed,
                    progress_percentage=0,
                    failure_reason=f"Blocked: waiting for {failed_stage}",
                )
                completed_units += 1
                await self._update_parent_progress(parent_job_id, completed_units, total_units)
                continue

            if not self._dependencies_satisfied(node.stage, context):
                dependency_stage = self._first_missing_dependency(node.stage, context) or "upstream stage"
                await self.pipeline.update_status(
                    job_id,
                    JobStatus.failed,
                    progress_percentage=0,
                    failure_reason=f"Blocked: waiting for {dependency_stage}",
                )
                completed_units += 1
                await self._update_parent_progress(parent_job_id, completed_units, total_units)
                continue

            await self.pipeline.update_status(job_id, JobStatus.running, progress_percentage=10)
            logger.info(stage_message("started", stage=node.stage, db_id=database_id, job_id=job_id))
            try:
                stage_output = await self._execute_stage(node.stage, database_id, parent_job_id, job_id, context=context)
                self._store_context(node.stage, context, stage_output)
                await self.pipeline.update_status(job_id, JobStatus.completed, progress_percentage=100)
                logger.info(stage_message("completed", stage=node.stage, db_id=database_id, job_id=job_id))
            except Exception as exc:
                await self.pipeline.update_status(job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)
                logger.error(error_message("stage failed", stage=node.stage, db_id=database_id, job_id=job_id, reason=exc), exc_info=True)
                failed_stage = failed_stage or node.stage
                if await self._can_retry(job_id):
                    await self.pipeline.retry_job(job_id, triggered_by="orchestrator")
            completed_units += 1
            await self._update_parent_progress(parent_job_id, completed_units, total_units)

        # Parent completion: mark failed if any child failed
        failed_children = await self._count_failed_children(parent_job_id)
        if failed_children > 0:
            await self.pipeline.update_status(
                parent_job_id,
                JobStatus.failed,
                progress_percentage=100,
                failure_reason=f"{failed_children} child job(s) failed",
            )
            logger.warning(error_message("orchestrator completed with failures", parent_job_id=parent_job_id, failed_children=failed_children))
            return

        await self.pipeline.update_status(parent_job_id, JobStatus.completed, progress_percentage=100)
        logger.info(sync_message("orchestrator run completed", parent_job_id=parent_job_id, db_id=database_id))

    async def _execute_stage(self, stage: str, database_id: int, parent_job_id: int, job_id: int, *, context: IntelligenceContext | None = None) -> Any:
        if stage == "metadata":
            return {"database_id": database_id, "stage": stage}
        if stage == "governance":
            return await self._run_governance(database_id, parent_job_id, job_id)
        if stage == "semantics":
            return await self._run_semantics(database_id, parent_job_id, job_id)
        if stage == "relationships":
            return await RelationshipGraphEngine(self.db).build_relationship_graph(database_id, persist=True)
        if stage == "kpi":
            return await KPIIntelligenceService(self.db).generate_for_database(database_id, job_id=job_id, context=context)
        if stage == "prompt":
            return await PromptStudioService(self.db).generate_artifacts(database_id, context=context)
        if stage == "embeddings":
            return await EmbeddingEngine(self.db).generate_database_embeddings(database_id, context=context)
        if stage == "readiness":
            return await ReadinessService(self.db).recompute(database_id, context=context)
        raise ValueError(f"Unknown stage {stage}")

    @staticmethod
    def _store_context(stage: str, context: IntelligenceContext, payload: Any) -> None:
        if stage == "governance":
            context.governance = GovernanceContext(packages=list(payload or []))
        elif stage == "semantics":
            context.semantics = SemanticContext(package=payload if isinstance(payload, dict) else None)
        elif stage == "relationships":
            context.relationships = RelationshipContext(packages=list((payload or {}).get("packages", []) if isinstance(payload, dict) else []))
        elif stage == "kpi":
            context.kpis = KPIContext(package=payload if isinstance(payload, dict) else None, catalog=list((payload or {}).get("catalog", []) if isinstance(payload, dict) else []))
        elif stage == "prompt":
            context.prompts = PromptContext(artifacts=list((payload or {}).get("artifacts", []) if isinstance(payload, dict) else []), package=payload if isinstance(payload, dict) else None)
        elif stage == "embeddings":
            context.embeddings = EmbeddingContext(status=payload if isinstance(payload, dict) else {})
        elif stage == "readiness":
            context.readiness = payload if isinstance(payload, dict) else None

    @staticmethod
    def _dependencies_satisfied(stage: str, context: IntelligenceContext) -> bool:
        if stage == "metadata":
            return True
        if stage == "governance":
            return True
        if stage == "semantics":
            return context.governance is not None
        if stage == "relationships":
            return context.governance is not None and context.semantics is not None
        if stage == "kpi":
            return context.governance is not None and context.semantics is not None and context.relationships is not None
        if stage == "prompt":
            return context.governance is not None and context.semantics is not None and context.relationships is not None and context.kpis is not None
        if stage == "embeddings":
            return context.governance is not None and context.semantics is not None and context.relationships is not None and context.kpis is not None and context.prompts is not None
        if stage == "readiness":
            return context.embeddings is not None and context.prompts is not None
        return True

    @staticmethod
    def _first_missing_dependency(stage: str, context: IntelligenceContext) -> str | None:
        checks = {
            "semantics": [("governance", context.governance)],
            "relationships": [("governance", context.governance), ("semantics", context.semantics)],
            "kpi": [("governance", context.governance), ("semantics", context.semantics), ("relationships", context.relationships)],
            "prompt": [("governance", context.governance), ("semantics", context.semantics), ("relationships", context.relationships), ("kpi", context.kpis)],
            "embeddings": [("governance", context.governance), ("semantics", context.semantics), ("relationships", context.relationships), ("kpi", context.kpis), ("prompt", context.prompts)],
            "readiness": [("embeddings", context.embeddings), ("prompt", context.prompts)],
        }
        for dep, value in checks.get(stage, []):
            if value is None:
                return dep
        return None

    async def _run_governance(self, database_id: int, parent_job_id: int, job_id: int) -> None:
        from app.services.column_semantic_service import ColumnSemanticService

        await ColumnSemanticService(self.db).generate_for_database(database_id, force=False)

    async def _run_semantics(self, database_id: int, parent_job_id: int, job_id: int) -> None:
        from app.services.database_semantic_service import DatabaseSemanticService
        await DatabaseSemanticService(self.db).generate_and_store_semantics(database_id)

    async def _can_retry(self, job_id: int) -> bool:
        job = await self.pipeline.get_job(job_id)
        return bool(job and job.retry_count < 2)

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        return await ensure_connected(self.db, database_id)

    async def _fetch_entities(self, database_id: int) -> list[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .options(
                selectinload(DatabaseTable.schema),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return result.scalars().all()

    async def _child_job_id(self, parent_job_id: int, job_type: JobType, table_id: int) -> Optional[int]:
        res = await self.db.execute(
            select(PipelineJob.id)
            .where(
                PipelineJob.parent_job_id == parent_job_id,
                PipelineJob.job_type == job_type,
                PipelineJob.entity_table_id == table_id,
            )
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def _stage_job_id(self, parent_job_id: int, stage_name: str) -> Optional[int]:
        res = await self.db.execute(
            select(PipelineJob.id)
            .where(
                PipelineJob.parent_job_id == parent_job_id,
                PipelineJob.stage_name == stage_name,
            )
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def _update_parent_progress(self, parent_job_id: int, completed_units: int, total_units: int) -> None:
        pct = max(1, min(99, int(round((completed_units / max(1, total_units)) * 100))))
        await self.pipeline.update_status(parent_job_id, JobStatus.running, progress_percentage=pct)

    async def _count_failed_children(self, parent_job_id: int) -> int:
        from sqlalchemy import func

        res = await self.db.execute(
            select(func.count(PipelineJob.id))
            .where(PipelineJob.parent_job_id == parent_job_id, PipelineJob.status == JobStatus.failed)
        )
        return int(res.scalar() or 0)

    async def get_stage_graph(self, database_id: int, parent_job_id: Optional[int] = None) -> dict[str, Any]:
        jobs = await self.db.execute(
            select(PipelineJob).where(PipelineJob.database_id == database_id)
        )
        job_rows = list(jobs.scalars().all())
        stages = []
        for node in STAGE_GRAPH:
            match = next((job for job in job_rows if job.stage_name == node.stage and (parent_job_id is None or job.parent_job_id == parent_job_id)), None)
            stages.append({
                "stage": node.stage,
                "status": match.status.value if match else "PENDING",
                "retries": match.retry_count if match else 0,
                "job_id": match.id if match else None,
                "depends_on": node.depends_on,
            })
        return {
            "database_id": database_id,
            "stages": stages,
            "graph": [{"stage": node.stage, "depends_on": node.depends_on} for node in STAGE_GRAPH],
            "resumable": True,
            "message": "Stage graph loaded.",
        }

    async def get_stage_progress(self, database_id: int, parent_job_id: Optional[int] = None) -> StageProgressResponse:
        jobs = await self.db.execute(
            select(PipelineJob).where(PipelineJob.database_id == database_id)
        )
        job_rows = list(jobs.scalars().all())
        filtered = [
            job for job in job_rows if parent_job_id is None or job.parent_job_id == parent_job_id or job.id == parent_job_id
        ]
        stage_items: list[StageProgressItem] = []
        completed = running = failed = pending = 0
        current_stage = None
        for node in STAGE_GRAPH:
            match = next((job for job in filtered if job.stage_name == node.stage), None)
            status = (match.status.value if match else "PENDING").lower()
            if match and match.failure_reason and str(match.failure_reason).startswith("Blocked:"):
                status = "blocked"
            progress = int(getattr(match, "progress_percentage", 0) or 0)
            stage_items.append(
                StageProgressItem(
                    stage=node.stage,
                    job_id=match.id if match else None,
                    status=status,
                    progress_percentage=progress,
                    retries=match.retry_count if match else 0,
                    failure_reason=match.failure_reason if match else None,
                    blocked_by_stage=(
                        str(match.failure_reason).split("Blocked: waiting for ", 1)[1]
                        if match and match.failure_reason and str(match.failure_reason).startswith("Blocked: waiting for ")
                        else None
                    ),
                    started_at=match.started_at if match else None,
                    completed_at=match.completed_at if match else None,
                    depends_on=node.depends_on,
                )
            )
            if status == "completed":
                completed += 1
            elif status == "running":
                running += 1
                current_stage = current_stage or node.stage
            elif status == "failed":
                failed += 1
                current_stage = current_stage or node.stage
            elif status == "blocked":
                pending += 1
            else:
                pending += 1

        total = max(1, len(stage_items))
        overall_progress = int(round((completed / total) * 100))
        overall_status = "completed" if completed == total else "failed" if failed else "running" if running else "pending"
        return StageProgressResponse(
            database_id=database_id,
            parent_job_id=parent_job_id,
            overall_status=overall_status,
            overall_progress_percentage=overall_progress,
            current_stage=current_stage,
            completed_stages=completed,
            running_stages=running,
            failed_stages=failed,
            pending_stages=pending,
            stages=stage_items,
            graph=[{"stage": node.stage, "depends_on": node.depends_on} for node in STAGE_GRAPH],
            message="Stage progress loaded.",
        )
