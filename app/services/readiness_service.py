"""
Deterministic AI readiness scoring service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
import logging

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
from app.config.package_registry import package_is_enabled
from app.config.manager import ConfigurationError, get_config_manager
from app.schema_engine.embeddings import EmbeddingEngine
from app.services.prompt_studio_service import PromptStudioService
from app.models.metadata import KPIArtifact, KPIIntelligence
from app.config.prompts import get_prompt_registry

logger = logging.getLogger(__name__)


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
    kpi_score: int
    kpi_readiness_score: int
    ai_summary: str | None
    ai_recommendations: list[str]
    ai_risks: list[str]
    ai_roadmap: list[str]
    ai_confidence: float
    prompt_id: str | None
    prompt_version: str | None
    model_name: str | None
    category_scores: dict[str, int]
    missing_stages: list[str]
    remediation_hints: list[str]
    details: dict[str, Any]


@dataclass
class PromptInventoryItem:
    prompt: str
    category: str
    executed: bool
    loaded_only: bool
    consumer: str


class ReadinessService:
    """Computes deterministic AI-readiness scores from existing metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()
        self.config = get_config_manager()
        self.readiness_rules = self._load_readiness_rules()

    def _load_readiness_rules(self) -> dict[str, Any]:
        rules = self.config.get_readiness_rules()
        readiness = rules.get("readiness")
        if not isinstance(readiness, dict):
            raise ConfigurationError("readiness_rules.yaml must define readiness")

        dimensions = readiness.get("dimensions")
        weights = readiness.get("weights")
        thresholds = readiness.get("thresholds")
        stages = readiness.get("stages")
        kpi_rules = readiness.get("kpi")

        if not isinstance(dimensions, list) or not dimensions:
            raise ConfigurationError("readiness.dimensions must be a non-empty list")
        if not isinstance(weights, dict) or not weights:
            raise ConfigurationError("readiness.weights must be a non-empty mapping")
        if not isinstance(thresholds, dict) or not thresholds:
            raise ConfigurationError("readiness.thresholds must be defined")
        if not isinstance(stages, list) or not stages:
            raise ConfigurationError("readiness.stages must be a non-empty list")
        if not isinstance(kpi_rules, dict) or not kpi_rules:
            raise ConfigurationError("readiness.kpi must be defined")

        configured_dimensions = self._readiness_packages_from_registry()
        if not configured_dimensions:
            raise ConfigurationError("No readiness-enabled packages are configured")
        configured_dimension_set = set(configured_dimensions)
        declared_dimension_set = {str(item) for item in dimensions}
        if declared_dimension_set != configured_dimension_set:
            raise ConfigurationError(
                "readiness.dimensions must match readiness-enabled packages in app/config/packages.yaml"
            )

        missing_weights = [dimension for dimension in configured_dimensions if dimension not in weights]
        if missing_weights:
            raise ConfigurationError(f"Missing readiness weights for: {', '.join(missing_weights)}")

        weight_total = round(sum(float(weights[name]) for name in configured_dimensions), 6)
        if abs(weight_total - 1.0) > 0.001:
            raise ConfigurationError(f"Readiness weights must sum to 1.0, got {weight_total}")

        return readiness

    def _readiness_dimensions(self) -> list[str]:
        return self._readiness_packages_from_registry()

    def _readiness_packages_from_registry(self) -> list[str]:
        package_config = self.config.get_packages().get("packages", {})
        return [
            package_name
            for package_name, package in package_config.items()
            if bool(package.get("readiness_enabled", False))
        ]

    def _readiness_weights(self) -> dict[str, float]:
        return {str(key): float(value) for key, value in (self.readiness_rules.get("weights", {}) or {}).items()}

    def _readiness_rules_thresholds(self) -> dict[str, Any]:
        return dict(self.readiness_rules.get("thresholds", {}) or {})

    def _kpi_rules(self) -> dict[str, Any]:
        return dict(self.readiness_rules.get("kpi", {}) or {})

    def _package_enabled(self, package_name: str) -> bool:
        if package_name == "kpi":
            return bool(self._kpi_rules().get("enabled", True)) and package_is_enabled(package_name)
        return package_is_enabled(package_name)

    def _enabled_packages(self) -> list[str]:
        return [name for name in self._readiness_dimensions() if self._package_enabled(name)]

    def _readiness_prompt_names(self) -> list[str]:
        return [prompt_path for prompt_path in self.registry.list_prompts() if prompt_path.startswith("readiness/")]

    def _readiness_assessment_prompt(self) -> str:
        prompts = self._readiness_prompt_names()
        for prompt_path in prompts:
            if not prompt_path.endswith("governance_readiness"):
                return prompt_path
        if prompts:
            return prompts[0]
        raise ConfigurationError("No readiness prompts are registered")

    @staticmethod
    def _prompt_consumers() -> dict[str, str]:
        return {
            "semantic": "app.services.database_semantic_service",
            "relationship": "app.schema_engine.relationship_graph",
            "kpi": "app.services.kpi_intelligence_service",
            "readiness": "app.services.readiness_service",
            "system": "app.services.prompt_studio_service",
        }

    def _prompt_inventory(self) -> list[PromptInventoryItem]:
        consumers = self._prompt_consumers()
        inventory: list[PromptInventoryItem] = []
        for entry in self.registry.list_prompts():
            category, prompt_id = entry.split("/", 1) if "/" in entry else ("", entry)
            consumer = consumers.get(category, "unknown")
            if category == "semantic" and prompt_id == "pii_classification":
                consumer = "app.services.column_semantic_service"
            elif category == "relationship":
                consumer = "app.schema_engine.relationship_graph"
            elif category == "readiness":
                consumer = "app.services.readiness_service"
            elif category == "system":
                consumer = "app.services.prompt_studio_service"
            elif category == "kpi":
                consumer = "app.services.kpi_intelligence_service"
            executed = consumer != "unknown"
            inventory.append(
                PromptInventoryItem(
                    prompt=prompt_id,
                    category=category,
                    executed=executed,
                    loaded_only=not executed,
                    consumer=consumer,
                )
            )
        return inventory

    def _enabled_artifacts(self) -> list[str]:
        artifacts: list[str] = []
        for package_name in self._readiness_dimensions():
            if not self._package_enabled(package_name):
                continue
            artifacts.extend(package_artifacts(package_name))
        return list(dict.fromkeys(artifacts))

    async def get_or_compute(self, database_id: int) -> ReadinessBreakdown:
        if not self._package_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")
        snapshot = await self._latest_snapshot(database_id)
        database = await self._fetch_database(database_id)
        if snapshot is None:
            return await self.recompute(database_id)

        status = snapshot.readiness_status
        if database.last_sync_at and snapshot.generated_at < database.last_sync_at:
            return await self.recompute(database_id)

        return await self._build_breakdown(
            database_id,
            status_override=status,
            snapshot=snapshot,
        )

    async def recompute(self, database_id: int) -> ReadinessBreakdown:
        if not self._package_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")
        database = await self._fetch_database(database_id)
        observability = AIObservabilityService()
        breakdown = await self._build_breakdown(database_id)
        assessment_prompt = self._readiness_assessment_prompt()
        ai_assessment = {
            "ai_summary": self._fallback_ai_summary(breakdown),
            "ai_recommendations": self._fallback_recommendations(breakdown),
            "ai_risks": self._fallback_risks(breakdown),
            "ai_roadmap": self._fallback_roadmap(breakdown),
            "ai_confidence": round(min(1.0, breakdown.overall_score / 100.0), 3),
        }
        try:
            ai_assessment = await self._generate_ai_assessment(database, breakdown)
            with observability.observe(
                module="ai_readiness",
                artifact_type="readiness_snapshot",
                prompt_id=assessment_prompt.split("/", 1)[1],
                prompt_version="registry",
                database_id=database.id,
                database_name=database.display_name or database.name,
                model_name=settings.azure_openai_deployment,
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
                    kpi_score=breakdown.kpi_score,
                    overall_score=breakdown.overall_score,
                    ai_summary=ai_assessment["ai_summary"],
                    ai_recommendations=json.dumps(ai_assessment["ai_recommendations"], default=str),
                    ai_risks=json.dumps(ai_assessment["ai_risks"], default=str),
                    ai_roadmap=json.dumps(ai_assessment["ai_roadmap"], default=str),
                    ai_confidence=ai_assessment["ai_confidence"],
                    prompt_id=self._readiness_assessment_prompt().split("/", 1)[1],
                    prompt_version=rendered.metadata.version,
                    model_name=settings.azure_openai_deployment,
                    readiness_status=breakdown.readiness_status,
                )
                self.db.add(snapshot)
                await self.db.flush()
                breakdown.generated_at = snapshot.generated_at
                breakdown.ai_summary = snapshot.ai_summary
                breakdown.ai_recommendations = self._parse_snapshot_json(snapshot.ai_recommendations)
                breakdown.ai_risks = self._parse_snapshot_json(snapshot.ai_risks)
                breakdown.ai_roadmap = self._parse_snapshot_json(snapshot.ai_roadmap)
                breakdown.ai_confidence = float(snapshot.ai_confidence)
                breakdown.prompt_id = snapshot.prompt_id
                breakdown.prompt_version = snapshot.prompt_version
                breakdown.model_name = snapshot.model_name
                if observation is not None:
                    observation.add_outputs(
                        {
                            "overall_score": breakdown.overall_score,
                            "category_scores": breakdown.category_scores,
                            "ai_summary": ai_assessment["ai_summary"],
                            "readiness_status": breakdown.readiness_status.value,
                        }
                    )
                    observation.add_metadata(
                        {
                            "database_id": database.id,
                            "database_name": database.display_name or database.name,
                            "module": "ai_readiness",
                            "artifact_type": "readiness_snapshot",
                            "prompt_version": rendered.metadata.version,
                            "model": settings.azure_openai_deployment,
                            "readiness_category": "overall",
                            "score_generated": breakdown.overall_score,
                            "completeness_score": breakdown.metadata_readiness_score / 100.0,
                            "coverage_score": breakdown.ai_context_readiness_score / 100.0,
                            "confidence_score": breakdown.overall_score / 100.0,
                        }
                    )
                    observation.end(outputs={
                        "overall_score": breakdown.overall_score,
                        "category_scores": breakdown.category_scores,
                        "readiness_status": breakdown.readiness_status.value,
                    })
                return breakdown
        except Exception:
            logger.exception("Readiness tracing failed; continuing without LangSmith update")
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
                kpi_score=breakdown.kpi_score,
                overall_score=breakdown.overall_score,
                ai_summary=ai_assessment["ai_summary"],
                ai_recommendations=json.dumps(ai_assessment["ai_recommendations"], default=str),
                ai_risks=json.dumps(ai_assessment["ai_risks"], default=str),
                ai_roadmap=json.dumps(ai_assessment["ai_roadmap"], default=str),
                ai_confidence=ai_assessment["ai_confidence"],
                prompt_id=self._readiness_assessment_prompt().split("/", 1)[1],
                prompt_version=rendered.metadata.version,
                model_name=settings.azure_openai_deployment,
                readiness_status=breakdown.readiness_status,
            )
            self.db.add(snapshot)
            await self.db.flush()
            breakdown.generated_at = snapshot.generated_at
            breakdown.ai_summary = snapshot.ai_summary
            breakdown.ai_recommendations = self._parse_snapshot_json(snapshot.ai_recommendations)
            breakdown.ai_risks = self._parse_snapshot_json(snapshot.ai_risks)
            breakdown.ai_roadmap = self._parse_snapshot_json(snapshot.ai_roadmap)
            breakdown.ai_confidence = float(snapshot.ai_confidence)
            breakdown.prompt_id = snapshot.prompt_id
            breakdown.prompt_version = snapshot.prompt_version
            breakdown.model_name = snapshot.model_name
            return breakdown

    async def _build_breakdown(
        self,
        database_id: int,
        status_override: ReadinessStatus | None = None,
        snapshot: ReadinessSnapshot | None = None,
    ) -> ReadinessBreakdown:
        database = await self._fetch_database(database_id)
        stats = await self._collect_stats(database_id)

        metadata_score = self._metadata_score(stats)
        semantic_score = self._semantic_score(stats)
        relationship_score = self._relationship_score(stats)
        ai_context_score = self._ai_context_score(stats)
        governance_score = self._governance_score(stats)
        kpi_score = self._kpi_score(stats)
        overall_score = self._overall_score(
            metadata_score,
            semantic_score,
            relationship_score,
            ai_context_score,
            governance_score,
            kpi_score,
        )

        category_scores = {
            "metadata_readiness_score": metadata_score,
            "semantic_readiness_score": semantic_score,
            "relationship_readiness_score": relationship_score,
            "ai_context_readiness_score": ai_context_score,
            "governance_readiness_score": governance_score,
            "kpi_readiness_score": kpi_score,
        }

        missing_stages, hints = self._build_remediation(stats, category_scores)
        status = status_override or self._status_from_score(overall_score, category_scores, missing_stages)

        details = {
            "metadata": stats["metadata"],
            "semantic": stats["semantic"],
            "relationships": stats["relationships"],
            "ai_context": stats["ai_context"],
            "governance": stats["governance"],
            "kpi": stats["kpi"],
            "embeddings": stats["embeddings"],
            "nosql": stats["nosql"],
            "snapshot": self._snapshot_details(snapshot),
        }

        # Legacy scores remain available for backward compatibility with older clients.
        legacy_scores = self._legacy_scores(category_scores, stats)
        hydrated_ai = self._hydrate_ai_snapshot(snapshot, breakdown_fallback={
            "ai_summary": None,
            "ai_recommendations": [],
            "ai_risks": [],
            "ai_roadmap": [],
            "ai_confidence": 0.0,
        })

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
            kpi_score=kpi_score,
            kpi_readiness_score=kpi_score,
            ai_summary=hydrated_ai["ai_summary"],
            ai_recommendations=hydrated_ai["ai_recommendations"],
            ai_risks=hydrated_ai["ai_risks"],
            ai_roadmap=hydrated_ai["ai_roadmap"],
            ai_confidence=hydrated_ai["ai_confidence"],
            prompt_id=hydrated_ai["prompt_id"],
            prompt_version=hydrated_ai["prompt_version"],
            model_name=hydrated_ai["model_name"],
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

    @staticmethod
    def _parse_snapshot_json(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except Exception:
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if parsed is None:
            return []
        return [str(parsed)]

    @classmethod
    def _hydrate_ai_snapshot(
        cls,
        snapshot: ReadinessSnapshot | None,
        *,
        breakdown_fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if snapshot is None:
            return dict(breakdown_fallback)
        return {
            "ai_summary": snapshot.ai_summary or breakdown_fallback["ai_summary"],
            "ai_recommendations": cls._parse_snapshot_json(snapshot.ai_recommendations) or breakdown_fallback["ai_recommendations"],
            "ai_risks": cls._parse_snapshot_json(snapshot.ai_risks) or breakdown_fallback["ai_risks"],
            "ai_roadmap": cls._parse_snapshot_json(snapshot.ai_roadmap) or breakdown_fallback["ai_roadmap"],
            "ai_confidence": float(snapshot.ai_confidence if snapshot.ai_confidence is not None else breakdown_fallback["ai_confidence"]),
            "prompt_id": snapshot.prompt_id,
            "prompt_version": snapshot.prompt_version,
            "model_name": snapshot.model_name,
        }

    @staticmethod
    def _snapshot_details(snapshot: ReadinessSnapshot | None) -> dict[str, Any]:
        if snapshot is None:
            return {}
        return {
            "prompt_id": snapshot.prompt_id,
            "prompt_version": snapshot.prompt_version,
            "model_name": snapshot.model_name,
            "ai_summary": snapshot.ai_summary,
            "ai_confidence": snapshot.ai_confidence,
        }

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
        relationship_ai_rows = await self.db.scalar(
            select(func.count(SchemaRelationshipGraph.id))
            .where(
                SchemaRelationshipGraph.database_id == database_id,
                SchemaRelationshipGraph.ai_summary.is_not(None),
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
        readiness_prompt_names = self._readiness_prompt_names()
        enabled_artifacts = self._enabled_artifacts()
        if tables > 0:
            try:
                prompt_context = await PromptStudioService(self.db)._build_context(database_id)
                for template_id in enabled_artifacts:
                    try:
                        rendered = self.registry.render_prompt(template_id, prompt_context, category="system")
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
            "relationship_intelligence": int(relationship_ai_rows),
            "isolated_tables": max(0, int(tables) - len(graph_table_ids)),
            "graph_table_ids": len(graph_table_ids),
        }

        pii_identified_coverage = self._ratio_score(int(column_semantics), int(columns))
        pii_classified_coverage = self._ratio_score(int(pii_typed_columns), max(1, int(pii_columns)))

        governance_stats = {
            "column_semantics": int(column_semantics),
            "pii_columns": int(pii_columns),
            "pii_typed_columns": int(pii_typed_columns),
            "pii_risk_tagged_columns": int(pii_risk_tagged_columns),
            "pii_identified_coverage": pii_identified_coverage,
            "pii_classified_coverage": pii_classified_coverage,
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

        kpi_count = 0
        kpi_artifacts = 0
        kpi_artifact_fresh = False
        kpi_confidence = 0.0
        if package_is_enabled("kpi"):
            try:
                kpi_count = int(
                    await self.db.scalar(
                        select(func.count(KPIIntelligence.id)).where(KPIIntelligence.database_id == database_id)
                    )
                    or 0
                )
                kpi_artifacts = int(
                    await self.db.scalar(
                        select(func.count(KPIArtifact.id)).where(KPIArtifact.database_id == database_id)
                    )
                    or 0
                )
                latest_kpi_artifact = await self.db.execute(
                    select(KPIArtifact)
                    .where(KPIArtifact.database_id == database_id)
                    .order_by(KPIArtifact.generated_at.desc())
                    .limit(1)
                )
                latest_kpi_artifact = latest_kpi_artifact.scalars().first()
                kpi_artifact_fresh = bool(
                    latest_kpi_artifact
                    and (not database.last_sync_at or latest_kpi_artifact.generated_at >= database.last_sync_at)
                )
                kpi_confidence = float(
                    await self.db.scalar(
                        select(func.coalesce(func.avg(KPIIntelligence.confidence), 0.0)).where(
                            KPIIntelligence.database_id == database_id
                        )
                    )
                    or 0.0
                )
            except Exception:
                logger.exception("Failed to collect KPI readiness stats for database_id=%s", database_id)

        kpi_stats = {
            "enabled": package_is_enabled("kpi"),
            "kpi_count": kpi_count,
            "artifact_count": kpi_artifacts,
            "artifact_fresh": kpi_artifact_fresh,
            "coverage_score": self._ratio_score(kpi_count, max(1, int(columns) // 10 or 1)),
            "confidence_score": kpi_confidence,
        }

        if tables > 0:
            readiness_context = {
                "database_name": database.display_name or database.name,
                "database_type": database.db_type.value,
                "metadata": metadata_stats,
                "semantic": semantic_stats,
                "relationships": relationship_stats,
                "relationship_intelligence": int(relationship_ai_rows),
                "ai_context": ai_context_stats,
                "governance": governance_stats,
                "kpi": kpi_stats,
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
                "column_semantics": governance_stats["column_semantics"],
                "governance_settings": {
                    "prompt_protection_enabled": governance_stats["prompt_protection_enabled"],
                    "embedding_protection_enabled": governance_stats["embedding_protection_enabled"],
                },
            }
            for template_id in readiness_prompt_names:
                try:
                    category, prompt_id = template_id.split("/", 1)
                    rendered = self.registry.render_prompt(prompt_id, readiness_context, category=category)
                    if rendered.user_prompt.strip():
                        prompt_artifacts_rendered += 1
                except Exception as exc:
                    prompt_artifact_errors.append(f"{template_id}: {exc}")

        ai_context_stats = {
            "prompt_artifacts_rendered": prompt_artifacts_rendered,
            "prompt_artifacts_expected": len(enabled_artifacts) + len(readiness_prompt_names),
            "prompt_context_length": prompt_context_length,
            "prompt_artifact_errors": prompt_artifact_errors,
            "embedding_coverage": self._ratio_score(int(embedding_status.get("completed_tables", 0)), int(max(1, tables))),
            "semantic_dependency_coverage": semantic_stats["semantic_table_coverage"],
        }

        prompt_protection_enabled = bool(
            settings.pii_prompt_protection_enabled
            and governance_stats["column_semantics"] > 0
            and prompt_artifacts_rendered >= len(enabled_artifacts) + len(readiness_prompt_names)
            and not prompt_artifact_errors
        )
        embedding_protection_enabled = bool(
            settings.pii_embedding_protection_enabled
            and governance_stats["column_semantics"] > 0
            and governance_stats["pii_columns"] > 0
            and int(embedding_status.get("completed_tables", 0)) > 0
        )
        governance_stats["prompt_protection_enabled"] = prompt_protection_enabled
        governance_stats["embedding_protection_enabled"] = embedding_protection_enabled

        return {
            "metadata": metadata_stats,
            "semantic": semantic_stats,
            "relationships": relationship_stats,
            "relationship_intelligence": int(relationship_ai_rows),
            "ai_context": ai_context_stats,
            "governance": governance_stats,
            "kpi": kpi_stats,
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

    async def _generate_ai_assessment(self, database: ConnectedDatabase, breakdown: ReadinessBreakdown) -> dict[str, Any]:
        context = breakdown.details
        prompt_context = {
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "scores": {
                "overall_score": breakdown.overall_score,
                "metadata_score": breakdown.metadata_score,
                "semantic_score": breakdown.semantic_score,
                "relationship_score": breakdown.relationship_score,
                "prompt_score": breakdown.prompt_score,
                "governance_readiness_score": breakdown.governance_readiness_score,
                "kpi_readiness_score": breakdown.kpi_readiness_score,
            },
            "category_scores": breakdown.category_scores,
            "metadata": context.get("metadata", {}),
            "semantic": context.get("semantic", {}),
            "relationships": context.get("relationships", {}),
            "governance": context.get("governance", {}),
            "kpi": context.get("kpi", {}),
            "ai_context": context.get("ai_context", {}),
            "package_coverage": {
                "enabled_packages": self._enabled_packages(),
                "total_enabled": len(self._enabled_packages()),
                "expected_packages": len(self._readiness_dimensions()),
            },
        }

        try:
            assessment_prompt = self._readiness_assessment_prompt()
            category, prompt_id = assessment_prompt.split("/", 1)
            rendered = self.registry.render_prompt(prompt_id, prompt_context, category=category)
            observability = AIObservabilityService()
            ai_result = await observability.generate(
                operation="chat",
                module="ai_readiness",
                artifact_type="readiness_assessment",
                prompt_id=rendered.metadata.id,
                prompt_version=rendered.metadata.version,
                database_id=database.id,
                database_name=database.display_name or database.name,
                model_name=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": rendered.system_message},
                    {"role": "user", "content": rendered.user_prompt},
                ],
                request_kwargs={
                    "max_completion_tokens": 1200,
                    "response_format": {"type": "json_object"},
                },
                completeness_score=breakdown.metadata_readiness_score / 100.0,
                coverage_score=breakdown.ai_context_readiness_score / 100.0,
                confidence_score=breakdown.overall_score / 100.0,
                extra_metadata={
                    "database_id": database.id,
                    "module": "ai_readiness",
                    "job_id": None,
                    "prompt_id": rendered.metadata.id,
                    "prompt_version": rendered.metadata.version,
                },
            )
            parsed = self._parse_ai_assessment(ai_result.content or "")
            parsed["ai_confidence"] = float(parsed.get("confidence", 0.0))
            return {
                "ai_summary": parsed.get("executive_summary") or "Readiness assessment generated.",
                "ai_recommendations": parsed.get("recommendations") or [],
                "ai_risks": parsed.get("risks") or [],
                "ai_roadmap": parsed.get("readiness_roadmap") or [],
                "ai_confidence": float(parsed.get("confidence", 0.0) or 0.0),
            }
        except Exception:
            logger.exception("AI readiness assessment generation failed; falling back to deterministic summary")
            return {
                "ai_summary": self._fallback_ai_summary(breakdown),
                "ai_recommendations": self._fallback_recommendations(breakdown),
                "ai_risks": self._fallback_risks(breakdown),
                "ai_roadmap": self._fallback_roadmap(breakdown),
                "ai_confidence": round(min(1.0, breakdown.overall_score / 100.0), 3),
            }

    @staticmethod
    def _parse_ai_assessment(text: str) -> dict[str, Any]:
        payload = text.strip()
        if payload.startswith("```"):
            payload = "\n".join(payload.splitlines()[1:-1]).strip()
        if payload.startswith("{") and payload.endswith("}"):
            return json.loads(payload)
        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(payload[start : end + 1])
        return {}

    @staticmethod
    def _fallback_ai_summary(breakdown: ReadinessBreakdown) -> str:
        return (
            f"Overall readiness is {breakdown.overall_score}%. "
            f"Semantic, relationship, governance, and KPI signals indicate the database is "
            f"{breakdown.readiness_status.value.lower().replace('_', ' ')} for AI workflows."
        )

    @staticmethod
    def _fallback_recommendations(breakdown: ReadinessBreakdown) -> list[str]:
        stage_scores = {
            "metadata": breakdown.metadata_readiness_score,
            "semantic": breakdown.semantic_readiness_score,
            "relationship": breakdown.relationship_readiness_score,
            "ai context": breakdown.ai_context_readiness_score,
            "governance": breakdown.governance_readiness_score,
            "kpi": breakdown.kpi_readiness_score,
        }
        return [
            f"Focus on the lowest-scoring category: {min(stage_scores, key=stage_scores.get)}.",
            "Regenerate missing artifacts and refresh the pipeline after schema changes.",
        ]

    @staticmethod
    def _fallback_risks(breakdown: ReadinessBreakdown) -> list[str]:
        risks = []
        if breakdown.kpi_readiness_score < 85:
            risks.append("KPI intelligence may be incomplete or stale.")
        if breakdown.governance_readiness_score < 85:
            risks.append("Governance signals are not strong enough for safe downstream AI usage.")
        return risks or ["No critical risks detected from deterministic scoring."]

    @staticmethod
    def _fallback_roadmap(breakdown: ReadinessBreakdown) -> list[str]:
        return [
            "Stabilize metadata and governance coverage.",
            "Refresh semantic, relationship, and KPI intelligence after the next sync.",
            "Monitor readiness freshness after each pipeline run.",
        ]

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

    def _kpi_score(self, stats: dict[str, Any]) -> int:
        kpi = stats["kpi"]
        rules = self._kpi_rules()
        if not kpi["enabled"] or kpi["kpi_count"] < int(rules.get("min_kpi_count", 1)):
            return 0

        confidence = max(0, min(100, int(round(float(kpi["confidence_score"]) * 100))))
        freshness = 100 if kpi["artifact_fresh"] else 0
        weights = rules.get("weights", {})
        return max(
            0,
            min(
                100,
                int(
                    round(
                        float(weights.get("coverage", 0.40)) * kpi["coverage_score"]
                        + float(weights.get("freshness", 0.35)) * freshness
                        + float(weights.get("confidence", 0.25)) * confidence
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
        kpi_score: int,
    ) -> int:
        weights = self._readiness_weights()
        weighted = (
            metadata_score * weights["metadata"]
            + semantic_score * weights["semantic"]
            + relationship_score * weights["relationship"]
            + ai_context_score * weights["ai_context"]
            + governance_score * weights["governance"]
            + kpi_score * weights["kpi"]
        )
        return max(0, min(100, int(round(weighted))))

    def readiness_prompt_inventory(self) -> list[dict[str, Any]]:
        return [
            {
                "prompt": item.prompt,
                "category": item.category,
                "executed": item.executed,
                "loaded_only": item.loaded_only,
                "consumer": item.consumer,
            }
            for item in self._prompt_inventory()
        ]

    def _status_from_score(
        self,
        overall_score: int,
        category_scores: dict[str, int],
        missing_stages: list[str],
    ) -> ReadinessStatus:
        thresholds = self._readiness_rules_thresholds()
        ready = thresholds.get("ready", {})
        partial = thresholds.get("partial", {})
        not_ready = thresholds.get("not_ready", {})
        ready_min = int(ready.get("min_score", 85))
        partial_min = int(partial.get("min_score", 40))
        ready_missing_allowed = int(ready.get("missing_stages_allowed", 0))
        ready_min_category = int(ready.get("min_category_score", 70))
        if overall_score >= ready_min and len(missing_stages) <= ready_missing_allowed and min(category_scores.values() or [0]) >= ready_min_category:
            return ReadinessStatus.READY
        if overall_score >= partial_min and overall_score >= int(not_ready.get("max_score", 40)):
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

        if category_scores.get("kpi_readiness_score", 0) < 85:
            missing.append("kpi")
            if not stats["kpi"]["enabled"]:
                hints.append("Enable the KPI package in the registry to generate KPI intelligence.")
            elif stats["kpi"]["kpi_count"] == 0:
                hints.append("Generate KPI intelligence to populate the KPI catalog and lineage artifacts.")
            elif not stats["kpi"]["artifact_fresh"]:
                hints.append("Refresh KPI artifacts after the latest schema sync.")

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
