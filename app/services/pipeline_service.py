"""
Pipeline operations service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import ConnectedDatabase
from app.models.pipeline_job import JobStatus, JobType, PipelineJob


@dataclass
class PipelineRunResult:
    database_id: int
    created_job_ids: list[int]
    message: str


class PipelineService:
    """Create and manage pipeline jobs for operational visibility."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_pipeline_run(
        self,
        database_id: int,
        triggered_by: Optional[str] = None,
    ) -> PipelineRunResult:
        await self._ensure_database(database_id)
        created: list[int] = []
        for job_type in (
            JobType.sync,
            JobType.semantic,
            JobType.embeddings,
            JobType.relationship_graph,
            JobType.exports,
        ):
            job = await self.create_job(database_id, job_type, triggered_by=triggered_by)
            created.append(job.id)

        return PipelineRunResult(
            database_id=database_id,
            created_job_ids=created,
            message=f"Queued {len(created)} pipeline jobs for database {database_id}",
        )

    async def create_job(
        self,
        database_id: int,
        job_type: JobType,
        triggered_by: Optional[str] = None,
        parent_job_id: Optional[int] = None,
        entity_table_id: Optional[int] = None,
        entity_name: Optional[str] = None,
    ) -> PipelineJob:
        await self._ensure_database(database_id)
        job = PipelineJob(
            parent_job_id=parent_job_id,
            job_type=job_type,
            database_id=database_id,
            entity_table_id=entity_table_id,
            entity_name=entity_name,
            status=JobStatus.queued,
            progress_percentage=0,
            triggered_by=triggered_by,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def list_jobs(
        self,
        limit: int = 100,
        status: Optional[JobStatus] = None,
    ) -> list[PipelineJob]:
        stmt = select(PipelineJob).order_by(desc(PipelineJob.started_at)).limit(limit)
        if status is not None:
            stmt = stmt.where(PipelineJob.status == status)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_job(self, job_id: int) -> Optional[PipelineJob]:
        result = await self.db.execute(
            select(PipelineJob).where(PipelineJob.id == job_id)
        )
        return result.scalars().first()

    async def update_status(
        self,
        job_id: int,
        status: JobStatus,
        progress_percentage: Optional[int] = None,
        failure_reason: Optional[str] = None,
    ) -> PipelineJob:
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Pipeline job {job_id} not found")

        job.status = status
        if progress_percentage is not None:
            job.progress_percentage = max(0, min(100, int(progress_percentage)))
        if failure_reason is not None:
            job.failure_reason = failure_reason

        if status == JobStatus.running:
            job.started_at = datetime.now(timezone.utc)
        if status in (JobStatus.failed, JobStatus.completed, JobStatus.cancelled):
            if job.completed_at is None:
                job.completed_at = datetime.now(timezone.utc)
            if status == JobStatus.completed and progress_percentage is None:
                job.progress_percentage = 100
        await self.db.flush()
        return job

    async def retry_job(self, job_id: int, triggered_by: Optional[str] = None) -> PipelineJob:
        current = await self.get_job(job_id)
        if not current:
            raise ValueError(f"Pipeline job {job_id} not found")

        retried = PipelineJob(
            job_type=current.job_type,
            database_id=current.database_id,
            status=JobStatus.queued,
            progress_percentage=0,
            triggered_by=triggered_by or current.triggered_by,
        )
        self.db.add(retried)
        await self.db.flush()
        return retried

    async def cancel_job(self, job_id: int) -> PipelineJob:
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Pipeline job {job_id} not found")
        if job.status in (JobStatus.completed, JobStatus.cancelled):
            return job
        return await self.update_status(
            job_id=job_id,
            status=JobStatus.cancelled,
            failure_reason=job.failure_reason or "Cancelled by user",
        )

    async def job_history(self, database_id: Optional[int] = None, limit: int = 100) -> list[PipelineJob]:
        stmt = select(PipelineJob).order_by(desc(PipelineJob.started_at)).limit(limit)
        if database_id is not None:
            stmt = stmt.where(PipelineJob.database_id == database_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _ensure_database(self, database_id: int) -> None:
        result = await self.db.execute(
            select(ConnectedDatabase.id).where(ConnectedDatabase.id == database_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Database {database_id} not found")
