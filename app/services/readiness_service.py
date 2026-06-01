"""
Deterministic AI readiness scoring service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    EmbeddingStatus,
    SchemaEmbedding,
    SchemaRelationshipGraph,
    SchemaSemantic,
)
from app.models.readiness_snapshot import ReadinessSnapshot, ReadinessStatus
from app.models.nosql_metadata import NoSQLCollection, NoSQLRelationship, NoSQLSchemaField
from app.schema_engine.prompt_builder import PromptBuilder


@dataclass
class ReadinessBreakdown:
    database_id: int
    database_name: str
    generated_at: datetime
    readiness_status: ReadinessStatus
    metadata_score: int
    semantic_score: int
    embeddings_score: int
    relationship_score: int
    prompt_score: int
    overall_score: int
    missing_stages: list[str]
    remediation_hints: list[str]
    details: dict[str, Any]


class ReadinessService:
    """Computes deterministic AI-readiness scores from existing metadata."""

    WEIGHTS = {
        "metadata": 0.25,
        "semantic": 0.25,
        "embeddings": 0.20,
        "relationships": 0.15,
        "prompt": 0.15,
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_compute(self, database_id: int) -> ReadinessBreakdown:
        snapshot = await self._latest_snapshot(database_id)
        database = await self._fetch_database(database_id)
        if snapshot is None:
            return await self.recompute(database_id)

        status = snapshot.readiness_status
        if database.last_sync_at and snapshot.generated_at < database.last_sync_at:
            status = ReadinessStatus.STALE

        breakdown = await self._build_breakdown(database_id, status_override=status)
        return breakdown

    async def recompute(self, database_id: int) -> ReadinessBreakdown:
        breakdown = await self._build_breakdown(database_id)
        snapshot = ReadinessSnapshot(
            database_id=database_id,
            metadata_score=breakdown.metadata_score,
            semantic_score=breakdown.semantic_score,
            embeddings_score=breakdown.embeddings_score,
            relationship_score=breakdown.relationship_score,
            prompt_score=breakdown.prompt_score,
            overall_score=breakdown.overall_score,
            readiness_status=breakdown.readiness_status,
        )
        self.db.add(snapshot)
        await self.db.flush()
        breakdown.generated_at = snapshot.generated_at
        return breakdown

    async def _build_breakdown(
        self,
        database_id: int,
        status_override: ReadinessStatus | None = None,
    ) -> ReadinessBreakdown:
        database = await self._fetch_database(database_id)
        stats = await self._collect_stats(database_id)

        metadata_score = self._metadata_score(stats)
        semantic_score = self._ratio_score(stats["semantic_tables"], stats["tables"])
        embeddings_score = self._ratio_score(stats["embedding_completed"], stats["tables"])
        relationship_score = self._relationship_score(stats)
        prompt_score = await self._prompt_score(database_id, stats)
        overall_score = self._overall_score(
            metadata_score,
            semantic_score,
            embeddings_score,
            relationship_score,
            prompt_score,
        )

        missing_stages, hints = self._build_remediation(stats, {
            "metadata": metadata_score,
            "semantic": semantic_score,
            "embeddings": embeddings_score,
            "relationships": relationship_score,
            "prompt": prompt_score,
        })
        status = status_override or self._status_from_score(overall_score, missing_stages)

        details = {
            "schemas": stats["schemas"],
            "tables": stats["tables"],
            "columns": stats["columns"],
            "relationships": stats["relationships"],
            "semantic_tables": stats["semantic_tables"],
            "embedding_completed": stats["embedding_completed"],
            "tables_with_graph_edges": stats["tables_with_graph_edges"],
            "tables_with_prompt_context": stats["tables_with_prompt_context"],
            "nosql_collections_inferred": stats["nosql_collections_inferred"],
            "nosql_nested_fields": stats["nosql_nested_fields"],
            "nosql_relationships": stats["nosql_relationships"],
        }

        return ReadinessBreakdown(
            database_id=database.id,
            database_name=database.display_name or database.name,
            generated_at=datetime.now(timezone.utc),
            readiness_status=status,
            metadata_score=metadata_score,
            semantic_score=semantic_score,
            embeddings_score=embeddings_score,
            relationship_score=relationship_score,
            prompt_score=prompt_score,
            overall_score=overall_score,
            missing_stages=missing_stages,
            remediation_hints=hints,
            details=details,
        )

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _latest_snapshot(self, database_id: int) -> ReadinessSnapshot | None:
        result = await self.db.execute(
            select(ReadinessSnapshot)
            .where(ReadinessSnapshot.database_id == database_id)
            .order_by(ReadinessSnapshot.generated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _collect_stats(self, database_id: int) -> dict[str, int]:
        schemas = await self.db.scalar(
            select(func.count(DatabaseSchema.id)).where(DatabaseSchema.connected_db_id == database_id)
        ) or 0
        tables = await self.db.scalar(
            select(func.count(DatabaseTable.id))
            .select_from(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        ) or 0
        columns = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        ) or 0
        relationships = await self.db.scalar(
            select(func.count(DatabaseRelationship.id))
            .select_from(DatabaseRelationship)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        ) or 0
        semantic_tables = await self.db.scalar(
            select(func.count(SchemaSemantic.id)).where(SchemaSemantic.database_id == database_id)
        ) or 0
        embedding_completed = await self.db.scalar(
            select(func.count(SchemaEmbedding.id))
            .select_from(SchemaEmbedding)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                SchemaEmbedding.embedding_status == EmbeddingStatus.completed,
            )
        ) or 0
        tables_with_graph_edges = await self.db.scalar(
            select(func.count(func.distinct(SchemaRelationshipGraph.source_table_id))).where(
                SchemaRelationshipGraph.database_id == database_id
            )
        ) or 0
        # NoSQL tables may not exist yet on older deployments; keep readiness resilient.
        try:
            nosql_collections_inferred = await self.db.scalar(
                select(func.count(NoSQLCollection.id)).where(NoSQLCollection.database_id == database_id)
            ) or 0
            nosql_nested_fields = await self.db.scalar(
                select(func.count(NoSQLSchemaField.id))
                .select_from(NoSQLSchemaField)
                .join(NoSQLCollection, NoSQLCollection.id == NoSQLSchemaField.collection_id)
                .where(
                    NoSQLCollection.database_id == database_id,
                    NoSQLSchemaField.nested_depth > 0,
                )
            ) or 0
            nosql_relationships = await self.db.scalar(
                select(func.count(NoSQLRelationship.id))
                .select_from(NoSQLRelationship)
                .join(NoSQLCollection, NoSQLCollection.id == NoSQLRelationship.collection_id)
                .where(NoSQLCollection.database_id == database_id)
            ) or 0
        except Exception:
            nosql_collections_inferred = 0
            nosql_nested_fields = 0
            nosql_relationships = 0

        tables_with_prompt_context = 0
        if tables > 0:
            # Prompt readiness is derived from semantic context availability.
            prompt_builder = PromptBuilder(self.db)
            context = await prompt_builder.build_semantic_context(database_id)
            if context and len(context.strip()) > 50:
                tables_with_prompt_context = tables

        return {
            "schemas": int(schemas),
            "tables": int(tables),
            "columns": int(columns),
            "relationships": int(relationships),
            "semantic_tables": int(semantic_tables),
            "embedding_completed": int(embedding_completed),
            "tables_with_graph_edges": int(tables_with_graph_edges),
            "tables_with_prompt_context": int(tables_with_prompt_context),
            "nosql_collections_inferred": int(nosql_collections_inferred),
            "nosql_nested_fields": int(nosql_nested_fields),
            "nosql_relationships": int(nosql_relationships),
        }

    @staticmethod
    def _ratio_score(numerator: int, denominator: int) -> int:
        if denominator <= 0:
            return 0
        return max(0, min(100, int(round((numerator / denominator) * 100))))

    def _metadata_score(self, stats: dict[str, int]) -> int:
        score = 0
        if stats["schemas"] > 0:
            score += 25
        if stats["tables"] > 0:
            score += 25
        if stats["columns"] > 0:
            score += 30
        if stats["relationships"] > 0:
            score += 20
        return score

    def _relationship_score(self, stats: dict[str, int]) -> int:
        tables = stats["tables"]
        if tables <= 0:
            return 0
        if tables == 1:
            return 100

        coverage = self._ratio_score(stats["tables_with_graph_edges"], tables)
        density = self._ratio_score(stats["relationships"], max(1, tables - 1))
        return max(0, min(100, int(round(0.7 * coverage + 0.3 * density))))

    async def _prompt_score(self, database_id: int, stats: dict[str, int]) -> int:
        tables = stats["tables"]
        if tables <= 0:
            return 0
        context_coverage = self._ratio_score(stats["tables_with_prompt_context"], tables)
        semantic_dependency = self._ratio_score(stats["semantic_tables"], tables)
        return max(0, min(100, int(round(0.6 * context_coverage + 0.4 * semantic_dependency))))

    def _overall_score(
        self,
        metadata_score: int,
        semantic_score: int,
        embeddings_score: int,
        relationship_score: int,
        prompt_score: int,
    ) -> int:
        weighted = (
            metadata_score * self.WEIGHTS["metadata"]
            + semantic_score * self.WEIGHTS["semantic"]
            + embeddings_score * self.WEIGHTS["embeddings"]
            + relationship_score * self.WEIGHTS["relationships"]
            + prompt_score * self.WEIGHTS["prompt"]
        )
        return max(0, min(100, int(round(weighted))))

    def _status_from_score(self, overall_score: int, missing_stages: list[str]) -> ReadinessStatus:
        if overall_score >= 85 and not missing_stages:
            return ReadinessStatus.READY
        if overall_score >= 40:
            return ReadinessStatus.PARTIAL
        return ReadinessStatus.NOT_READY

    def _build_remediation(self, stats: dict[str, int], scores: dict[str, int]) -> tuple[list[str], list[str]]:
        missing: list[str] = []
        hints: list[str] = []

        tables = stats["tables"]
        if scores["metadata"] < 100:
            missing.append("metadata")
            if stats["schemas"] == 0 or stats["tables"] == 0 or stats["columns"] == 0:
                hints.append("Run schema sync to populate core metadata.")
            elif stats["relationships"] == 0:
                hints.append("No relationships detected; verify FK metadata extraction.")

        semantic_missing = max(0, tables - stats["semantic_tables"])
        if semantic_missing > 0:
            missing.append("semantic")
            hints.append(f"Semantic enrichment incomplete for {semantic_missing} entities.")

        embedding_missing = max(0, tables - stats["embedding_completed"])
        if embedding_missing > 0:
            missing.append("embeddings")
            hints.append(f"Embeddings missing for {embedding_missing} entities.")

        if scores["relationships"] < 70:
            missing.append("relationships")
            hints.append("Relationship quality is low; rebuild relationship graph and verify join metadata.")
            if stats["nosql_collections_inferred"] > 0 and stats["nosql_relationships"] == 0:
                hints.append("NoSQL relationship inference missing; run Mongo schema inference.")
        if stats["nosql_collections_inferred"] > 0 and stats["nosql_nested_fields"] == 0:
            missing.append("metadata")
            hints.append("Nested NoSQL structure inference is incomplete.")

        if scores["prompt"] < 100:
            missing.append("prompt")
            hints.append("Prompt context generation readiness is incomplete.")

        # Preserve order while deduplicating
        missing = list(dict.fromkeys(missing))
        hints = list(dict.fromkeys(hints))
        return missing, hints
