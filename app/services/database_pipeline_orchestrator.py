"""
Database-level orchestration for AI context generation.

External UX: database-level "Generate AI Context".
Internal execution: entity-level processing with operational tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, DatabaseType
from app.models.pipeline_job import JobStatus, JobType
from app.schema_engine.embeddings import EmbeddingEngine
from app.schema_engine.enricher import SchemaEnricher
from app.schema_engine.prompt_builder import PromptBuilder
from app.services.artifact_service import ArtifactService
from app.services.mongodb_service import MongoDBService
from app.services.pipeline_service import PipelineService
from app.services.readiness_service import ReadinessService

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorRunResult:
    parent_job_id: int
    entity_count: int
    message: str


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

        # Create child jobs now (so Operations UI can display immediately)
        for table in entities:
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=JobType.semantic,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                entity_table_id=table.id,
                entity_name=f"{table.schema.name}.{table.name}",
            )
            await self.pipeline.create_job(
                database_id=database_id,
                job_type=JobType.embeddings,
                triggered_by=triggered_by,
                parent_job_id=parent.id,
                entity_table_id=table.id,
                entity_name=f"{table.schema.name}.{table.name}",
            )

        # Create db-level jobs for aggregation stages
        await self.pipeline.create_job(
            database_id=database_id,
            job_type=JobType.relationship_graph,
            triggered_by=triggered_by,
            parent_job_id=parent.id,
        )
        await self.pipeline.create_job(
            database_id=database_id,
            job_type=JobType.prompt,
            triggered_by=triggered_by,
            parent_job_id=parent.id,
        )
        await self.pipeline.create_job(
            database_id=database_id,
            job_type=JobType.readiness,
            triggered_by=triggered_by,
            parent_job_id=parent.id,
        )
        await self.pipeline.create_job(
            database_id=database_id,
            job_type=JobType.artifact_packaging,
            triggered_by=triggered_by,
            parent_job_id=parent.id,
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
        total_units = max(1, len(entities) * 2 + 4)  # semantic+embedding per entity + db stages
        completed_units = 0

        # Run per-entity semantic then embeddings
        enricher = SchemaEnricher(self.db)
        embedder = EmbeddingEngine(self.db)

        for table in entities:
            if (await self.pipeline.get_job(parent_job_id)).status == JobStatus.cancelled:
                await self.pipeline.update_status(parent_job_id, JobStatus.cancelled)
                return

            semantic_job_id = await self._child_job_id(parent_job_id, JobType.semantic, table.id)
            if semantic_job_id:
                await self.pipeline.update_status(semantic_job_id, JobStatus.running, progress_percentage=10)
                try:
                    enrichment = await enricher.enrich_table(table.id)
                    await enricher.save_enrichment(self.db, enrichment)
                    await self.pipeline.update_status(semantic_job_id, JobStatus.completed, progress_percentage=100)
                except Exception as exc:
                    await self.pipeline.update_status(
                        semantic_job_id,
                        JobStatus.failed,
                        failure_reason=str(exc),
                        progress_percentage=0,
                    )
            completed_units += 1
            await self._update_parent_progress(parent_job_id, completed_units, total_units)

            embedding_job_id = await self._child_job_id(parent_job_id, JobType.embeddings, table.id)
            if embedding_job_id:
                await self.pipeline.update_status(embedding_job_id, JobStatus.running, progress_percentage=10)
                try:
                    await embedder.generate_table_embeddings(database_id, table.id)
                    await self.pipeline.update_status(embedding_job_id, JobStatus.completed, progress_percentage=100)
                except Exception as exc:
                    await self.pipeline.update_status(
                        embedding_job_id,
                        JobStatus.failed,
                        failure_reason=str(exc),
                        progress_percentage=0,
                    )
            completed_units += 1
            await self._update_parent_progress(parent_job_id, completed_units, total_units)

        # Relationship graph (db-level)
        rel_job_id = await self._db_stage_job_id(parent_job_id, JobType.relationship_graph)
        if rel_job_id:
            await self.pipeline.update_status(rel_job_id, JobStatus.running, progress_percentage=10)
        try:
            from app.schema_engine.relationship_graph import RelationshipGraphEngine

            await RelationshipGraphEngine(self.db).build_relationship_graph(database_id, persist=True)
            if rel_job_id:
                await self.pipeline.update_status(rel_job_id, JobStatus.completed, progress_percentage=100)
        except Exception as exc:
            if rel_job_id:
                await self.pipeline.update_status(rel_job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)
        completed_units += 1
        await self._update_parent_progress(parent_job_id, completed_units, total_units)

        # Prompt package (db-level, derived from semantics)
        prompt_job_id = await self._db_stage_job_id(parent_job_id, JobType.prompt)
        if prompt_job_id:
            await self.pipeline.update_status(prompt_job_id, JobStatus.running, progress_percentage=10)
        try:
            _ = await PromptBuilder(self.db).build_semantic_context(database_id)
            if prompt_job_id:
                await self.pipeline.update_status(prompt_job_id, JobStatus.completed, progress_percentage=100)
        except Exception as exc:
            if prompt_job_id:
                await self.pipeline.update_status(prompt_job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)
        completed_units += 1
        await self._update_parent_progress(parent_job_id, completed_units, total_units)

        # Readiness (db-level)
        readiness_job_id = await self._db_stage_job_id(parent_job_id, JobType.readiness)
        if readiness_job_id:
            await self.pipeline.update_status(readiness_job_id, JobStatus.running, progress_percentage=10)
        try:
            await ReadinessService(self.db).recompute(database_id)
            if readiness_job_id:
                await self.pipeline.update_status(readiness_job_id, JobStatus.completed, progress_percentage=100)
        except Exception as exc:
            if readiness_job_id:
                await self.pipeline.update_status(readiness_job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)
        completed_units += 1
        await self._update_parent_progress(parent_job_id, completed_units, total_units)

        # Artifact packaging (db-level)
        artifact_job_id = await self._db_stage_job_id(parent_job_id, JobType.artifact_packaging)
        if artifact_job_id:
            await self.pipeline.update_status(artifact_job_id, JobStatus.running, progress_percentage=10)
        try:
            await ArtifactService(self.db).export_artifacts(database_id)
            if artifact_job_id:
                await self.pipeline.update_status(artifact_job_id, JobStatus.completed, progress_percentage=100)
        except Exception as exc:
            if artifact_job_id:
                await self.pipeline.update_status(artifact_job_id, JobStatus.failed, failure_reason=str(exc), progress_percentage=0)

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

    async def _db_stage_job_id(self, parent_job_id: int, job_type: JobType) -> Optional[int]:
        from app.models.pipeline_job import PipelineJob

        res = await self.db.execute(
            select(PipelineJob.id)
            .where(
                PipelineJob.parent_job_id == parent_job_id,
                PipelineJob.job_type == job_type,
                PipelineJob.entity_table_id.is_(None),
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

