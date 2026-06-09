"""
Deterministic AI readiness scoring service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.column_semantic import ColumnSemantic
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    SchemaRelationshipGraph,
    SchemaSemantic,
)
from app.models.nosql_metadata import NoSQLCollection, NoSQLRelationship, NoSQLSchemaField
from app.models.readiness_snapshot import ReadinessSnapshot, ReadinessStatus
from app.core.config import settings
from app.services.ai_observability_service import AIObservabilityService
from app.schema_engine.embeddings import EmbeddingEngine
from app.services.prompt_studio_service import PromptStudioService
from app.config.prompts import get_prompt_registry


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
    metadata_readiness_score: int
    semantic_readiness_score: int
    relationship_readiness_score: int
    ai_context_readiness_score: int
    governance_readiness_score: int
    category_scores: dict[str, int]
    missing_stages: list[str]
    remediation_hints: list[str]
    details: dict[str, Any]


class ReadinessService:
    """Computes deterministic AI-readiness scores from existing metadata."""

    WEIGHTS = {
        "metadata": 0.24,
        "semantic": 0.24,
        "relationship": 0.20,
        "ai_context": 0.18,
        "governance": 0.14,
    }

    REQUIRED_ARTIFACT_TEMPLATES = (
        "database_context",
        "system_prompt",
        "rag_context",
        "agent_context",
        "text_to_sql",
    )

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

        return await self._build_breakdown(database_id, status_override=status)

    async def recompute(self, database_id: int) -> ReadinessBreakdown:
        database = await self._fetch_database(database_id)
        observability = AIObservabilityService()
        breakdown = await self._build_breakdown(database_id)
        with observability.observe(
            module="ai_readiness",
            artifact_type="readiness_snapshot",
            prompt_id="readiness_rules",
            prompt_version="1",
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name="deterministic",
            completeness_score=breakdown.metadata_readiness_score / 100.0,
            coverage_score=breakdown.ai_context_readiness_score / 100.0,
            confidence_score=breakdown.overall_score / 100.0,
            extra_metadata={
                "readiness_category": "overall",
            },
        ) as observation:
            snapshot = ReadinessSnapshot(
                database_id=database_id,
                metadata_score=breakdown.metadata_score,
                semantic_score=breakdown.semantic_score,
                embeddings_score=breakdown.embeddings_score,
                relationship_score=breakdown.relationship_score,
                prompt_score=breakdown.prompt_score,
                metadata_readiness_score=breakdown.metadata_readiness_score,
                semantic_readiness_score=breakdown.semantic_readiness_score,
                relationship_readiness_score=breakdown.relationship_readiness_score,
                ai_context_readiness_score=breakdown.ai_context_readiness_score,
                governance_readiness_score=breakdown.governance_readiness_score,
                overall_score=breakdown.overall_score,
                prompt_id="readiness_rules",
                prompt_version="1",
                model_name="deterministic",
                readiness_status=breakdown.readiness_status,
            )
            self.db.add(snapshot)
            await self.db.flush()
            breakdown.generated_at = snapshot.generated_at
            if observation is not None:
                observation.update(
                    output={
                        "overall_score": breakdown.overall_score,
                        "category_scores": breakdown.category_scores,
                        "readiness_status": breakdown.readiness_status.value,
                    },
                    metadata={
                        "database_id": database.id,
                        "database_name": database.display_name or database.name,
                        "module": "ai_readiness",
                        "artifact_type": "readiness_snapshot",
                        "prompt_version": "1",
                        "model": "deterministic",
                        "readiness_category": "overall",
                        "score_generated": breakdown.overall_score,
                        "completeness_score": breakdown.metadata_readiness_score / 100.0,
                        "coverage_score": breakdown.ai_context_readiness_score / 100.0,
                        "confidence_score": breakdown.overall_score / 100.0,
                    },
                )
            return breakdown

    async def _build_breakdown(
        self,
        database_id: int,
        status_override: ReadinessStatus | None = None,
    ) -> ReadinessBreakdown:
        database = await self._fetch_database(database_id)
        stats = await self._collect_stats(database_id)

        metadata_score = self._metadata_score(stats)
        semantic_score = self._semantic_score(stats)
        relationship_score = self._relationship_score(stats)
        ai_context_score = self._ai_context_score(stats)
        governance_score = self._governance_score(stats)
        overall_score = self._overall_score(
            metadata_score,
            semantic_score,
            relationship_score,
            ai_context_score,
            governance_score,
        )

        category_scores = {
            "metadata_readiness_score": metadata_score,
            "semantic_readiness_score": semantic_score,
            "relationship_readiness_score": relationship_score,
            "ai_context_readiness_score": ai_context_score,
            "governance_readiness_score": governance_score,
        }

        missing_stages, hints = self._build_remediation(stats, category_scores)
        status = status_override or self._status_from_score(overall_score, category_scores, missing_stages)

        details = {
            "metadata": stats["metadata"],
            "semantic": stats["semantic"],
            "relationships": stats["relationships"],
            "ai_context": stats["ai_context"],
            "governance": stats["governance"],
            "embeddings": stats["embeddings"],
            "nosql": stats["nosql"],
        }

        # Legacy scores remain available for backward compatibility with older clients.
        legacy_scores = self._legacy_scores(category_scores, stats)

        return ReadinessBreakdown(
            database_id=database.id,
            database_name=database.display_name or database.name,
            generated_at=datetime.now(timezone.utc),
            readiness_status=status,
            metadata_score=legacy_scores["metadata_score"],
            semantic_score=legacy_scores["semantic_score"],
            embeddings_score=legacy_scores["embeddings_score"],
            relationship_score=legacy_scores["relationship_score"],
            prompt_score=legacy_scores["prompt_score"],
            overall_score=overall_score,
            metadata_readiness_score=metadata_score,
            semantic_readiness_score=semantic_score,
            relationship_readiness_score=relationship_score,
            ai_context_readiness_score=ai_context_score,
            governance_readiness_score=governance_score,
            category_scores=category_scores,
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

    async def _fetch_database_semantic(self, database_id: int) -> DatabaseSemantic | None:
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        return result.scalars().first()

    @staticmethod
    def _ratio_score(numerator: int, denominator: int) -> int:
        if denominator <= 0:
            return 0
        return max(0, min(100, int(round((numerator / denominator) * 100))))

    @staticmethod
    def _presence_score(*values: bool) -> int:
        if not values:
            return 0
        return int(round(sum(1 for value in values if value) / len(values) * 100))

    async def _collect_stats(self, database_id: int) -> dict[str, Any]:
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
            .join(
                DatabaseTable,
                DatabaseRelationship.table_id == DatabaseTable.id,
            )
            .join(
                DatabaseSchema,
                DatabaseTable.schema_id == DatabaseSchema.id,
            )
            .where(DatabaseSchema.connected_db_id == database_id)
        ) or 0
        schemas_with_description = await self.db.scalar(
            select(func.count(DatabaseSchema.id))
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseSchema.description.is_not(None),
                func.length(func.trim(DatabaseSchema.description)) > 0,
            )
        ) or 0
        tables_with_description = await self.db.scalar(
            select(func.count(DatabaseTable.id))
            .select_from(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseTable.description.is_not(None),
                func.length(func.trim(DatabaseTable.description)) > 0,
            )
        ) or 0
        columns_with_description = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseColumn.description.is_not(None),
                func.length(func.trim(DatabaseColumn.description)) > 0,
            )
        ) or 0
        tables_with_row_count = await self.db.scalar(
            select(func.count(DatabaseTable.id))
            .select_from(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseTable.row_count.is_not(None),
            )
        ) or 0
        primary_key_columns = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseColumn.is_primary_key.is_(True),
            )
        ) or 0
        foreign_key_columns = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseColumn.is_foreign_key.is_(True),
            )
        ) or 0
        indexed_columns = await self.db.scalar(
            select(func.count(DatabaseColumn.id))
            .select_from(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseColumn.is_indexed.is_(True),
            )
        ) or 0
        schema_semantics = await self.db.scalar(
            select(func.count(SchemaSemantic.id)).where(SchemaSemantic.database_id == database_id)
        ) or 0
        column_semantics = await self.db.scalar(
            select(func.count(ColumnSemantic.id)).where(ColumnSemantic.database_id == database_id)
        ) or 0
        pii_columns = await self.db.scalar(
            select(func.count(ColumnSemantic.id))
            .where(
                ColumnSemantic.database_id == database_id,
                ColumnSemantic.is_pii.is_(True),
            )
        ) or 0
        pii_typed_columns = await self.db.scalar(
            select(func.count(ColumnSemantic.id))
            .where(
                ColumnSemantic.database_id == database_id,
                ColumnSemantic.is_pii.is_(True),
                ColumnSemantic.pii_type.is_not(None),
            )
        ) or 0
        pii_risk_tagged_columns = await self.db.scalar(
            select(func.count(ColumnSemantic.id))
            .where(
                ColumnSemantic.database_id == database_id,
                ColumnSemantic.is_pii.is_(True),
                ColumnSemantic.risk_level.is_not(None),
            )
        ) or 0

        database_semantic = await self._fetch_database_semantic(database_id)

        graph_rows = await self.db.execute(
            select(
                SchemaRelationshipGraph.source_table_id,
                SchemaRelationshipGraph.target_table_id,
            ).where(SchemaRelationshipGraph.database_id == database_id)
        )
        graph_edges = graph_rows.all()
        graph_edge_count = len(graph_edges)
        graph_table_ids = {table_id for row in graph_edges for table_id in row if table_id is not None}
        graph_cycles = await self.db.scalar(
            select(func.count(SchemaRelationshipGraph.id))
            .where(
                SchemaRelationshipGraph.database_id == database_id,
                SchemaRelationshipGraph.is_circular.is_(True),
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

        embedding_engine = EmbeddingEngine(self.db)
        try:
            embedding_status = await embedding_engine.get_embedding_status(database_id)
        except Exception:
            embedding_status = {
                "indexed_tables": 0,
                "completed_tables": 0,
                "failed_tables": 0,
                "vectors_total": 0,
                "vector_counts": {},
                "collections": [],
                "qdrant_health": False,
                "embedding_health": False,
                "total_tables": tables,
            }

        prompt_context = {}
        prompt_artifact_errors: list[str] = []
        prompt_artifacts_rendered = 0
        prompt_context_length = 0
        if tables > 0:
            try:
                prompt_context = await PromptStudioService(self.db)._build_context(database_id)
                registry = get_prompt_registry()
                for template_id in self.REQUIRED_ARTIFACT_TEMPLATES:
                    try:
                        rendered = registry.render_prompt(template_id, prompt_context, category="system")
                        if rendered.user_prompt.strip():
                            prompt_artifacts_rendered += 1
                        if template_id == "rag_context":
                            prompt_context_length = len(rendered.user_prompt.strip())
                    except Exception as exc:
                        prompt_artifact_errors.append(f"{template_id}: {exc}")
            except Exception as exc:
                prompt_artifact_errors.append(str(exc))

        semantic_profile = {
            "has_profile": database_semantic is not None,
            "business_domain": bool(database_semantic and database_semantic.business_domain),
            "business_summary": bool(database_semantic and database_semantic.business_summary),
            "analysis_notes": bool(database_semantic and database_semantic.analysis_notes),
            "key_entities": len(database_semantic.key_entities) if database_semantic else 0,
            "business_glossary": len(database_semantic.business_glossary) if database_semantic else 0,
            "suggested_use_cases": len(database_semantic.suggested_use_cases) if database_semantic else 0,
            "confidence_score": database_semantic.confidence_score if database_semantic else 0.0,
            "generation_status": database_semantic.generation_status.value if database_semantic else "not_generated",
        }

        metadata_stats = {
            "schemas": int(schemas),
            "tables": int(tables),
            "columns": int(columns),
            "relationships": int(relationships),
            "schemas_with_description": int(schemas_with_description),
            "tables_with_description": int(tables_with_description),
            "columns_with_description": int(columns_with_description),
            "tables_with_row_count": int(tables_with_row_count),
            "primary_key_columns": int(primary_key_columns),
            "foreign_key_columns": int(foreign_key_columns),
            "indexed_columns": int(indexed_columns),
        }

        semantic_stats = {
            "schema_semantics": int(schema_semantics),
            "semantic_table_coverage": self._ratio_score(int(schema_semantics), int(tables)),
            "profile": semantic_profile,
        }

        relationship_stats = {
            "graph_edges": int(graph_edge_count),
            "graph_table_coverage": self._ratio_score(len(graph_table_ids), int(tables)),
            "graph_density": self._relationship_density(int(graph_edge_count), int(tables)),
            "graph_cycles": int(graph_cycles),
            "isolated_tables": max(0, int(tables) - len(graph_table_ids)),
            "graph_table_ids": len(graph_table_ids),
        }

        ai_context_stats = {
            "prompt_artifacts_rendered": prompt_artifacts_rendered,
            "prompt_artifacts_expected": len(self.REQUIRED_ARTIFACT_TEMPLATES),
            "prompt_context_length": prompt_context_length,
            "prompt_artifact_errors": prompt_artifact_errors,
            "embedding_coverage": self._ratio_score(int(embedding_status.get("completed_tables", 0)), int(max(1, tables))),
            "semantic_dependency_coverage": semantic_stats["semantic_table_coverage"],
        }

        pii_identified_coverage = self._ratio_score(int(column_semantics), int(columns))
        pii_classified_coverage = self._ratio_score(int(pii_typed_columns), max(1, int(pii_columns)))
        prompt_protection_enabled = bool(
            settings.pii_prompt_protection_enabled and int(column_semantics) > 0
        )
        embedding_protection_enabled = bool(
            settings.pii_embedding_protection_enabled and int(column_semantics) > 0
        )

        governance_stats = {
            "column_semantics": int(column_semantics),
            "pii_columns": int(pii_columns),
            "pii_typed_columns": int(pii_typed_columns),
            "pii_risk_tagged_columns": int(pii_risk_tagged_columns),
            "pii_identified_coverage": pii_identified_coverage,
            "pii_classified_coverage": pii_classified_coverage,
            "prompt_protection_enabled": prompt_protection_enabled,
            "embedding_protection_enabled": embedding_protection_enabled,
            "documentation_coverage": self._documentation_coverage(
                int(schemas),
                int(tables),
                int(columns),
                int(schemas_with_description),
                int(tables_with_description),
                int(columns_with_description),
            ),
            "ownership_coverage": 0,
            "ownership_metadata_present": False,
            "pii_coverage": pii_identified_coverage,
        }

        return {
            "metadata": metadata_stats,
            "semantic": semantic_stats,
            "relationships": relationship_stats,
            "ai_context": ai_context_stats,
            "governance": governance_stats,
            "embeddings": {
                "indexed_tables": int(embedding_status.get("indexed_tables", 0)),
                "completed_tables": int(embedding_status.get("completed_tables", 0)),
                "failed_tables": int(embedding_status.get("failed_tables", 0)),
                "vectors_total": int(embedding_status.get("vectors_total", 0)),
                "qdrant_health": bool(embedding_status.get("qdrant_health", False)),
                "embedding_health": bool(embedding_status.get("embedding_health", False)),
                "total_tables": int(embedding_status.get("total_tables", tables)),
                "collections": embedding_status.get("collections", []),
                "vector_counts": embedding_status.get("vector_counts", {}),
            },
            "nosql": {
                "collections": int(nosql_collections_inferred),
                "nested_fields": int(nosql_nested_fields),
                "relationships": int(nosql_relationships),
            },
            "database_semantic": database_semantic,
        }

    def _metadata_score(self, stats: dict[str, Any]) -> int:
        metadata = stats["metadata"]
        schemas = metadata["schemas"]
        tables = metadata["tables"]
        columns = metadata["columns"]

        if schemas <= 0 or tables <= 0 or columns <= 0:
            return 0

        schema_presence = 100
        table_presence = 100
        column_presence = 100
        schema_doc_coverage = self._ratio_score(metadata["schemas_with_description"], schemas)
        table_doc_coverage = self._ratio_score(metadata["tables_with_description"], tables)
        column_doc_coverage = self._ratio_score(metadata["columns_with_description"], columns)

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.30 * schema_presence
                        + 0.20 * table_presence
                        + 0.15 * column_presence
                        + 0.15 * schema_doc_coverage
                        + 0.10 * table_doc_coverage
                        + 0.10 * column_doc_coverage
                    )
                ),
            ),
        )

    def _semantic_score(self, stats: dict[str, Any]) -> int:
        semantic = stats["semantic"]
        profile = semantic["profile"]
        tables = stats["metadata"]["tables"]
        if tables <= 0:
            return 0

        profile_completeness = self._presence_score(
            profile["business_domain"],
            profile["business_summary"],
            profile["analysis_notes"],
            profile["key_entities"] > 0,
            profile["business_glossary"] > 0,
            profile["suggested_use_cases"] > 0,
        )
        semantic_table_coverage = semantic["semantic_table_coverage"]
        glossary_target = max(1, min(5, profile["key_entities"] or 5))
        glossary_coverage = self._ratio_score(profile["business_glossary"], glossary_target)
        use_case_coverage = self._ratio_score(profile["suggested_use_cases"], 4)
        confidence = int(round(max(0.0, min(1.0, float(profile["confidence_score"]))) * 100))

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.25 * profile_completeness
                        + 0.30 * semantic_table_coverage
                        + 0.20 * glossary_coverage
                        + 0.15 * use_case_coverage
                        + 0.10 * confidence
                    )
                ),
            ),
        )

    def _relationship_score(self, stats: dict[str, Any]) -> int:
        metadata = stats["metadata"]
        raw_relationships = metadata["relationships"]
        tables = metadata["tables"]
        if tables <= 0:
            return 0
        if tables == 1:
            return 100

        relationship = stats["relationships"]
        graph_edges = relationship["graph_edges"]
        relationship_coverage = self._ratio_score(graph_edges, max(1, raw_relationships))
        graph_table_coverage = relationship["graph_table_coverage"]
        density = min(100, int(round(relationship["graph_density"] * 100)))
        cycle_penalty = max(0, 100 - relationship["graph_cycles"] * 15)
        isolation_penalty = max(0, 100 - relationship["isolated_tables"] * 12)

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.35 * graph_table_coverage
                        + 0.25 * relationship_coverage
                        + 0.20 * density
                        + 0.10 * cycle_penalty
                        + 0.10 * isolation_penalty
                    )
                ),
            ),
        )

    def _ai_context_score(self, stats: dict[str, Any]) -> int:
        ai_context = stats["ai_context"]
        metadata = stats["metadata"]
        tables = metadata["tables"]
        if tables <= 0:
            return 0

        artifact_coverage = self._ratio_score(
            ai_context["prompt_artifacts_rendered"],
            ai_context["prompt_artifacts_expected"],
        )
        embedding_coverage = ai_context["embedding_coverage"]
        semantic_dependency_coverage = ai_context["semantic_dependency_coverage"]

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.50 * artifact_coverage
                        + 0.30 * embedding_coverage
                        + 0.20 * semantic_dependency_coverage
                    )
                ),
            ),
        )

    def _governance_score(self, stats: dict[str, Any]) -> int:
        governance = stats["governance"]
        pii_identified = governance["pii_identified_coverage"]
        pii_classified = governance["pii_classified_coverage"]
        prompt_protection = 100 if governance["prompt_protection_enabled"] else 0
        embedding_protection = 100 if governance["embedding_protection_enabled"] else 0

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.30 * pii_identified
                        + 0.30 * pii_classified
                        + 0.20 * prompt_protection
                        + 0.20 * embedding_protection
                    )
                ),
            ),
        )

    def _overall_score(
        self,
        metadata_score: int,
        semantic_score: int,
        relationship_score: int,
        ai_context_score: int,
        governance_score: int,
    ) -> int:
        weighted = (
            metadata_score * self.WEIGHTS["metadata"]
            + semantic_score * self.WEIGHTS["semantic"]
            + relationship_score * self.WEIGHTS["relationship"]
            + ai_context_score * self.WEIGHTS["ai_context"]
            + governance_score * self.WEIGHTS["governance"]
        )
        return max(0, min(100, int(round(weighted))))

    def _status_from_score(
        self,
        overall_score: int,
        category_scores: dict[str, int],
        missing_stages: list[str],
    ) -> ReadinessStatus:
        if overall_score >= 85 and not missing_stages and min(category_scores.values() or [0]) >= 70:
            return ReadinessStatus.READY
        if overall_score >= 40:
            return ReadinessStatus.PARTIAL
        return ReadinessStatus.NOT_READY

    def _build_remediation(
        self,
        stats: dict[str, Any],
        category_scores: dict[str, int],
    ) -> tuple[list[str], list[str]]:
        missing: list[str] = []
        hints: list[str] = []

        metadata = stats["metadata"]
        semantic = stats["semantic"]
        relationships = stats["relationships"]
        ai_context = stats["ai_context"]
        governance = stats["governance"]
        embeddings = stats["embeddings"]

        if category_scores["metadata_readiness_score"] < 85:
            missing.append("metadata")
            if metadata["schemas"] == 0 or metadata["tables"] == 0 or metadata["columns"] == 0:
                hints.append("Run schema sync to populate schemas, tables, and columns.")
            if metadata["schemas_with_description"] < metadata["schemas"]:
                hints.append("Add schema descriptions to improve metadata completeness.")
            if metadata["tables_with_description"] < metadata["tables"]:
                hints.append("Add table descriptions to improve business context.")
            if metadata["columns_with_description"] < metadata["columns"]:
                hints.append("Add column descriptions to improve column-level documentation.")
            if metadata["tables_with_row_count"] < metadata["tables"]:
                hints.append("Capture table row counts to strengthen KPI readiness and data quality signals.")

        if category_scores["semantic_readiness_score"] < 85:
            missing.append("semantic")
            if not semantic["profile"]["has_profile"]:
                hints.append("Generate database semantic intelligence.")
            if not semantic["profile"]["business_summary"]:
                hints.append("Add a concise business summary for the database.")
            if semantic["profile"]["business_glossary"] == 0:
                hints.append("Populate the business glossary to improve semantic coverage.")
            if semantic["profile"]["suggested_use_cases"] == 0:
                hints.append("Define AI and analytics use cases for this dataset.")
            if semantic["schema_semantics"] < metadata["tables"]:
                hints.append("Generate table-level semantic summaries for all key entities.")

        if category_scores["relationship_readiness_score"] < 85:
            missing.append("relationships")
            if relationships["graph_edges"] == 0 and metadata["relationships"] > 0:
                hints.append("Build the relationship graph to persist join discovery results.")
            if metadata["relationships"] == 0 and metadata["tables"] > 1:
                hints.append("No foreign keys were discovered; verify join metadata extraction.")
            if relationships["isolated_tables"] > 0:
                hints.append("Some tables remain isolated; review relationship discovery coverage.")
            if relationships["graph_cycles"] > 0:
                hints.append("Relationship cycles were detected; review circular joins.")

        if category_scores["ai_context_readiness_score"] < 85:
            missing.append("ai_context")
            if ai_context["prompt_artifacts_rendered"] < ai_context["prompt_artifacts_expected"]:
                hints.append("Prompt package generation is incomplete; render the full Prompt Studio bundle.")
            if embeddings["completed_tables"] < embeddings["total_tables"]:
                hints.append("Embeddings are incomplete; finish vector indexing for all tables.")
            if ai_context["semantic_dependency_coverage"] < 100:
                hints.append("Semantic context is incomplete; regenerate semantic intelligence before packaging prompts.")
            if ai_context["prompt_artifact_errors"]:
                hints.append("One or more prompt templates failed to render cleanly.")

        if category_scores["governance_readiness_score"] < 85:
            missing.append("governance")
            if governance["column_semantics"] == 0 and metadata["columns"] > 0:
                hints.append("No column semantics or PII intelligence records exist yet.")
            if not governance["ownership_metadata_present"]:
                hints.append("Ownership metadata is not captured by the current schema.")
            if governance["documentation_coverage"] < 70:
                hints.append("Documentation coverage is low across schemas, tables, or columns.")
            if governance["pii_identified_coverage"] < 100 and metadata["columns"] > 0:
                hints.append("PII intelligence is incomplete; run column PII classification for all columns.")
            if governance["pii_classified_coverage"] < 100 and governance["pii_columns"] > 0:
                hints.append("Some PII columns are missing type labels; rerun PII classification.")
            if not governance["prompt_protection_enabled"]:
                hints.append("Enable prompt protection to redact PII from generated prompt artifacts.")
            if not governance["embedding_protection_enabled"]:
                hints.append("Enable embedding protection to exclude PII column details from vector indexes.")

        if governance["pii_risk_tagged_columns"] == 0 and governance["pii_columns"] > 0:
            hints.append("PII records exist, but risk labels are not populated for all sensitive fields.")

        missing = list(dict.fromkeys(missing))
        hints = list(dict.fromkeys(hints))
        return missing, hints

    @staticmethod
    def _documentation_coverage(
        schemas: int,
        tables: int,
        columns: int,
        schemas_with_description: int,
        tables_with_description: int,
        columns_with_description: int,
    ) -> int:
        if schemas <= 0 or tables <= 0 or columns <= 0:
            return 0

        schema_doc_coverage = schemas_with_description / schemas
        table_doc_coverage = tables_with_description / tables
        column_doc_coverage = columns_with_description / columns
        return max(0, min(100, int(round((0.35 * schema_doc_coverage + 0.35 * table_doc_coverage + 0.30 * column_doc_coverage) * 100))))

    def _legacy_scores(self, category_scores: dict[str, int], stats: dict[str, Any]) -> dict[str, int]:
        embeddings = stats["embeddings"]
        return {
            "metadata_score": category_scores["metadata_readiness_score"],
            "semantic_score": category_scores["semantic_readiness_score"],
            "embeddings_score": self._ratio_score(int(embeddings.get("completed_tables", 0)), int(max(1, embeddings.get("total_tables", 0)))),
            "relationship_score": category_scores["relationship_readiness_score"],
            "prompt_score": category_scores["ai_context_readiness_score"],
        }

    @staticmethod
    def _relationship_density(edge_count: int, tables: int) -> float:
        if tables <= 1:
            return 0.0
        return round(edge_count / (tables * (tables - 1) / 2), 4)
