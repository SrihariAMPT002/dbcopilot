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

from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, DatabaseType
from app.models.pipeline_job import JobStatus, JobType
from app.schema_engine.embeddings import EmbeddingEngine
from app.schema_engine.enricher import SchemaEnricher
from app.services.artifact_service import ArtifactService
from app.services.kpi_intelligence_service import KPIIntelligenceService
from app.services.mongodb_service import MongoDBService
from app.services.pipeline_service import PipelineService
from app.services.readiness_service import ReadinessService
from app.services.prompt_studio_service import PromptStudioService

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
    StageGraphNode("relationships", JobType.relationship_graph, ["semantics"], "Relationships"),
    StageGraphNode("kpi", JobType.kpi, ["relationships"], "KPI"),
    StageGraphNode("prompt", JobType.prompt, ["kpi"], "Prompt"),
    StageGraphNode("readiness", JobType.readiness, ["prompt"], "Readiness"),
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
                stage_name="semantics",
                depends_on=["governance"],
            )
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=JobType.embeddings,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                entity_table_id=table.id,
                entity_name=f"{table.schema.name}.{table.name}",
                stage_name="embeddings",
                depends_on=["metadata"],
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

        database_id = parent.database_id
        database = await self._fetch_database(database_id)

        # For MongoDB: ensure NoSQL registry exists (schema inference is a separate button per collection today).
        if database.db_type == DatabaseType.mongodb:
            try:
                await MongoDBService(self.db).ensure_collection_registry(database_id)
            except Exception as exc:
                logger.warning("Mongo registry refresh failed: %s", exc, exc_info=True)

        entities = await self._fetch_entities(database_id)
        total_units = max(1, len(entities) * 2 + len(STAGE_GRAPH))
        completed_units = 0

        # Run stage graph in order; each stage can resume independently.
        enricher = SchemaEnricher(self.db)
        embedder = EmbeddingEngine(self.db)

        for node in STAGE_GRAPH:
            if (await self.pipeline.get_job(parent_job_id)).status == JobStatus.cancelled:
                await self.pipeline.update_status(parent_job_id, JobStatus.cancelled)
                return

            job_id = await self._stage_job_id(parent_job_id, node.stage)
            if job_id is None:
                completed_units += 1
                continue

            await self.pipeline.update_status(job_id, JobStatus.running, progress_percentage=10)
            try:
                await self._execute_stage(node.stage, database_id, parent_job_id, job_id)
                await self.pipeline.update_status(job_id, JobStatus.completed, progress_percentage=100)
            except Exception as exc:
                await self.pipeline.update_status(job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)
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
            return

        await self.pipeline.update_status(parent_job_id, JobStatus.completed, progress_percentage=100)

    async def _execute_stage(self, stage: str, database_id: int, parent_job_id: int, job_id: int) -> None:
        if stage == "metadata":
            return
        if stage == "governance":
            return await self._run_governance(database_id, parent_job_id, job_id)
        if stage == "semantics":
            return await self._run_semantics(database_id, parent_job_id, job_id)
        if stage == "relationships":
            return await RelationshipGraphEngine(self.db).build_relationship_graph(database_id, persist=True)
        if stage == "kpi":
            return await KPIIntelligenceService(self.db).generate_for_database(database_id, job_id=job_id)
        if stage == "prompt":
            return await PromptStudioService(self.db).generate_artifacts(database_id)
        if stage == "readiness":
            return await ReadinessService(self.db).recompute(database_id)
        raise ValueError(f"Unknown stage {stage}")

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
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        db = result.scalars().first()
        if not db:
            raise ValueError(f"Database {database_id} not found")
        return db

    async def _fetch_entities(self, database_id: int) -> list[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return result.scalars().all()

    async def _child_job_id(self, parent_job_id: int, job_type: JobType, table_id: int) -> Optional[int]:
        from app.models.pipeline_job import PipelineJob

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
        from app.models.pipeline_job import PipelineJob

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
        from app.models.pipeline_job import PipelineJob

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
