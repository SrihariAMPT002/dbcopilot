"""
Deterministic AI readiness scoring service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
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
    GovernancePackage,
    SchemaRelationshipGraph,
    SchemaSemantic,
    RelationshipPackage,
    SemanticPackage,
)
from app.services.database_guard import ensure_connected
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
from app.models.remediation_action import RemediationAction
from app.services.remediation_service import RemediationService
from app.models.prompt_package import PromptPackage
from app.models.embedding_document import EmbeddingDocument
from app.models.retrieval_evaluation import RetrievalEvaluation
from app.models.retrieval_log import RetrievalLog
from app.models.semantic_cache import SemanticCache
from app.models.agent_memory import AgentMemory
from app.models.prompt_evaluation import PromptEvaluation
from app.services.pipeline_context import IntelligenceContext
from app.core.structured_logging import error_message

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
    kpi_cluster_count: int
    successful_cluster_count: int
    failed_cluster_count: int
    coverage_percentage: float
    ai_summary: str | None
    ai_recommendations: list[str]
    ai_risks: list[str]
    ai_roadmap: list[str]
    ai_confidence: float
    ai_narrative_status: str
    prompt_id: str | None
    prompt_version: str | None
    model_name: str | None
    context_source: str | None = None
    used_context: bool = False
    fallback_reason: str | None = None
    category_scores: dict[str, int] = field(default_factory=dict)
    missing_stages: list[str] = field(default_factory=list)
    remediation_hints: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


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

    @staticmethod
    def _stage_metadata_fingerprint(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, default=str, sort_keys=True).encode("utf-8")).hexdigest()[:32]

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

    @staticmethod
    def _normalize_ai_artifact(artifact: Any | None, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = artifact if isinstance(artifact, dict) else {}
        normalized = {
            "ai_summary": payload.get("ai_summary") or payload.get("executive_summary") or (fallback or {}).get("ai_summary"),
            "ai_recommendations": payload.get("ai_recommendations")
            or payload.get("recommendations")
            or (fallback or {}).get("ai_recommendations", []),
            "ai_risks": payload.get("ai_risks") or payload.get("risks") or (fallback or {}).get("ai_risks", []),
            "ai_roadmap": payload.get("ai_roadmap")
            or payload.get("readiness_roadmap")
            or (fallback or {}).get("ai_roadmap", []),
            "ai_confidence": payload.get("ai_confidence", payload.get("confidence", (fallback or {}).get("ai_confidence", 0.0))),
            "trace_id": payload.get("trace_id", (fallback or {}).get("trace_id")),
            "prompt_id": payload.get("prompt_id", (fallback or {}).get("prompt_id")),
            "prompt_version": payload.get("prompt_version", (fallback or {}).get("prompt_version")),
            "model_name": payload.get("model_name", (fallback or {}).get("model_name")),
            "token_metrics": payload.get("token_metrics", (fallback or {}).get("token_metrics", {})) or {},
            "execution_status": payload.get("execution_status", (fallback or {}).get("execution_status", "partial")),
            "fallback_used": bool(payload.get("fallback_used", (fallback or {}).get("fallback_used", False))),
            "retry_count": int(payload.get("retry_count", (fallback or {}).get("retry_count", 0)) or 0),
        }
        if not normalized["ai_summary"]:
            normalized["ai_summary"] = "Readiness assessment generated with partial metadata."
        normalized["ai_recommendations"] = list(normalized["ai_recommendations"] or [])
        normalized["ai_risks"] = list(normalized["ai_risks"] or [])
        normalized["ai_roadmap"] = list(normalized["ai_roadmap"] or [])
        try:
            normalized["ai_confidence"] = float(normalized["ai_confidence"] or 0.0)
        except Exception:
            normalized["ai_confidence"] = 0.0
        return normalized

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

    def _package_completeness(self, stats: dict[str, Any]) -> dict[str, Any]:
        enabled_packages = self._enabled_packages()
        package_flags = {
            "governance": bool(stats.get("governance_packages")),
            "semantic": bool(stats.get("semantic_package_present")),
            "relationship": bool(stats.get("relationship_packages")),
            "kpi": int(stats.get("kpi_cluster_count", 0) or 0) > 0,
            "prompt": int(stats.get("prompt_artifacts_rendered", 0) or 0) > 0,
            "embedding": int(stats.get("embeddings", {}).get("completed_tables", 0) or 0) > 0,
            "readiness": int(stats.get("readiness_snapshots", 0) or 0) > 0,
        }
        covered = sum(1 for key in package_flags if package_flags[key])
        return {
            "enabled_packages": enabled_packages,
            "coverage_ratio": round(covered / max(1, len(enabled_packages)), 3),
            "package_flags": package_flags,
        }

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
        latest_change = await self._latest_package_change_at(database_id)
        if snapshot is None:
            return await self.recompute(database_id)

        if latest_change and snapshot.generated_at < latest_change:
            return await self.recompute(database_id)

        if database.last_sync_at and snapshot.generated_at < database.last_sync_at:
            return await self.recompute(database_id)

        return await self._build_breakdown(
            database_id,
            status_override=snapshot.readiness_status,
            snapshot=snapshot,
        )

    async def recompute(self, database_id: int, context: IntelligenceContext | None = None) -> ReadinessBreakdown:
        if not self._package_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")
        database = await self._fetch_database(database_id)
        used_context = bool(context and (context.governance or context.semantics or context.relationships or context.kpis or context.prompts or context.embeddings))
        fallback_reason = None
        if used_context and not (context and context.governance):
            fallback_reason = fallback_reason or "governance"
        if used_context and not (context and context.semantics):
            fallback_reason = fallback_reason or "semantics"
        if used_context and not (context and context.relationships):
            fallback_reason = fallback_reason or "relationships"
        if used_context and not (context and context.kpis):
            fallback_reason = fallback_reason or "kpi"
        if used_context and not (context and context.prompts):
            fallback_reason = fallback_reason or "prompt"
        if used_context and not (context and context.embeddings):
            fallback_reason = fallback_reason or "embeddings"
        breakdown = await self._build_breakdown(database_id, context=context)
        ai_assessment = self._fallback_ai_assessment(breakdown)
        try:
            ai_assessment = await self._generate_ai_assessment(database, breakdown)
        except Exception:
            logger.exception(error_message("ai readiness assessment generation failed", fallback="deterministic summary"))

        snapshot = await self._upsert_snapshot(database.id, breakdown, ai_assessment)
        await self._persist_remediation_actions(snapshot, database.id, breakdown, ai_assessment)
        breakdown.generated_at = snapshot.generated_at
        breakdown.ai_summary = snapshot.ai_summary
        breakdown.ai_recommendations = self._parse_snapshot_json(snapshot.ai_recommendations)
        breakdown.ai_risks = self._parse_snapshot_json(snapshot.ai_risks)
        breakdown.ai_roadmap = self._parse_snapshot_json(snapshot.ai_roadmap)
        breakdown.ai_confidence = float(snapshot.ai_confidence)
        breakdown.ai_narrative_status = snapshot.execution_status or "failed"
        breakdown.prompt_id = snapshot.prompt_id
        breakdown.prompt_version = snapshot.prompt_version
        breakdown.model_name = snapshot.model_name
        breakdown.context_source = "runtime" if used_context else "persisted"
        breakdown.used_context = used_context
        breakdown.fallback_reason = fallback_reason
        breakdown.kpi_cluster_count = int(snapshot.kpi_cluster_count)
        breakdown.successful_cluster_count = int(snapshot.successful_cluster_count)
        breakdown.failed_cluster_count = int(snapshot.failed_cluster_count)
        breakdown.coverage_percentage = float(snapshot.coverage_percentage)
        return breakdown

    async def _persist_remediation_actions(
        self,
        snapshot: ReadinessSnapshot,
        database_id: int,
        breakdown: ReadinessBreakdown,
        ai_assessment: dict[str, Any],
    ) -> list[RemediationAction]:
        recommendations: list[dict[str, Any]] = []
        for hint in breakdown.remediation_hints[:10]:
            recommendations.append(
                {
                    "issue": hint,
                    "recommendation": hint,
                    "expected_impact": "Improve AI readiness coverage",
                    "priority": "medium",
                    "confidence_score": float(ai_assessment.get("ai_confidence", 0.0) or 0.0),
                    "evidence": [{"source": "readiness_snapshot", "snapshot_id": snapshot.id}],
                    "trace_id": ai_assessment.get("trace_id"),
                }
            )
        if not recommendations and ai_assessment.get("ai_recommendations"):
            for item in ai_assessment.get("ai_recommendations", [])[:10]:
                recommendations.append(
                    {
                        "issue": str(item),
                        "recommendation": str(item),
                        "expected_impact": "Improve AI readiness coverage",
                        "priority": "medium",
                        "confidence_score": float(ai_assessment.get("ai_confidence", 0.0) or 0.0),
                        "evidence": [{"source": "ai_assessment", "snapshot_id": snapshot.id}],
                        "trace_id": ai_assessment.get("trace_id"),
                    }
                )
        if not recommendations:
            return []
        service = RemediationService(self.db)
        return await service.persist(
            readiness_snapshot_id=snapshot.id,
            database_id=database_id,
            recommendations=recommendations,
            trace_id=ai_assessment.get("trace_id"),
        )

    async def _latest_package_change_at(self, database_id: int) -> datetime | None:
        candidates: list[datetime | None] = []

        async def _max_timestamp(model: Any, *, timestamp_column: str = "updated_at", clause: Any = None) -> None:
            column = getattr(model, timestamp_column, None)
            if column is None:
                column = getattr(model, "created_at", None)
            if column is None or not hasattr(model, "database_id"):
                return
            stmt = select(func.max(column)).where(model.database_id == database_id)
            if clause is not None:
                stmt = stmt.where(clause)
            result = await self.db.execute(stmt)
            candidates.append(result.scalar_one_or_none())

        await _max_timestamp(GovernancePackage)
        await _max_timestamp(SemanticPackage)
        await _max_timestamp(RelationshipPackage)
        await _max_timestamp(KPIIntelligence)
        await _max_timestamp(KPIArtifact)
        await _max_timestamp(ReadinessSnapshot)

        extra_models = [
            PromptPackage,
            EmbeddingDocument,
            RetrievalEvaluation,
            RetrievalLog,
            SemanticCache,
            AgentMemory,
            PromptEvaluation,
        ]
        for model in extra_models:
            await _max_timestamp(model)

        values = [value for value in candidates if value is not None]
        return max(values) if values else None

    async def _upsert_snapshot(self, database_id: int, breakdown: ReadinessBreakdown, ai_assessment: dict[str, Any]) -> ReadinessSnapshot:
        normalized = self._normalize_ai_artifact(ai_assessment, fallback={
            "ai_summary": self._fallback_ai_summary(breakdown),
            "ai_recommendations": self._fallback_recommendations(breakdown),
            "ai_risks": self._fallback_risks(breakdown),
            "ai_roadmap": self._fallback_roadmap(breakdown),
            "ai_confidence": round(min(1.0, breakdown.overall_score / 100.0), 3),
            "trace_id": None,
            "prompt_id": self._readiness_assessment_prompt().split("/", 1)[1],
            "prompt_version": "registry",
            "model_name": settings.azure_openai_deployment,
            "execution_status": "fallback",
            "fallback_used": True,
            "retry_count": 0,
        })
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
            kpi_cluster_count=breakdown.kpi_cluster_count,
            successful_cluster_count=breakdown.successful_cluster_count,
            failed_cluster_count=breakdown.failed_cluster_count,
            coverage_percentage=breakdown.coverage_percentage,
            ai_summary=normalized["ai_summary"],
            ai_recommendations=json.dumps(normalized["ai_recommendations"], default=str),
            ai_risks=json.dumps(normalized["ai_risks"], default=str),
            ai_roadmap=json.dumps(normalized["ai_roadmap"], default=str),
            ai_confidence=normalized["ai_confidence"],
            prompt_id=normalized["prompt_id"],
            prompt_version=normalized["prompt_version"],
            model_name=normalized["model_name"],
            execution_status=normalized["execution_status"],
            used_fallback=bool(normalized["fallback_used"]),
            retry_count=int(normalized["retry_count"]),
            trace_id=normalized["trace_id"],
            readiness_status=breakdown.readiness_status,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    def _fallback_ai_assessment(self, breakdown: ReadinessBreakdown) -> dict[str, Any]:
        return {
            "ai_summary": self._fallback_ai_summary(breakdown),
            "ai_recommendations": self._fallback_recommendations(breakdown),
            "ai_risks": self._fallback_risks(breakdown),
            "ai_roadmap": self._fallback_roadmap(breakdown),
            "ai_confidence": round(min(1.0, breakdown.overall_score / 100.0), 3),
            "execution_status": "fallback",
            "fallback_used": True,
            "retry_count": 0,
            "trace_id": None,
            "prompt_id": self._readiness_assessment_prompt().split("/", 1)[1],
            "prompt_version": "registry",
            "model_name": settings.azure_openai_deployment,
        }

    async def _build_breakdown(
        self,
        database_id: int,
        status_override: ReadinessStatus | None = None,
        snapshot: ReadinessSnapshot | None = None,
        context: IntelligenceContext | None = None,
    ) -> ReadinessBreakdown:
        database = await self._fetch_database(database_id)
        stats = await self._collect_stats(database_id, context=context)

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
            "trace_id": None,
            "prompt_id": self._readiness_assessment_prompt().split("/", 1)[1],
            "prompt_version": "registry",
            "model_name": settings.azure_openai_deployment,
            "token_metrics": {},
            "execution_status": "partial",
            "fallback_used": True,
            "retry_count": 0,
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
            kpi_cluster_count=int(stats["kpi"].get("kpi_cluster_count", 0) or 0),
            successful_cluster_count=int(stats["kpi"].get("successful_cluster_count", 0) or 0),
            failed_cluster_count=int(stats["kpi"].get("failed_cluster_count", 0) or 0),
            coverage_percentage=float(stats["kpi"].get("coverage_percentage", 0.0) or 0.0),
            ai_summary=hydrated_ai["ai_summary"],
            ai_recommendations=hydrated_ai["ai_recommendations"],
            ai_risks=hydrated_ai["ai_risks"],
            ai_roadmap=hydrated_ai["ai_roadmap"],
            ai_confidence=hydrated_ai["ai_confidence"],
            prompt_id=hydrated_ai.get("prompt_id"),
            prompt_version=hydrated_ai.get("prompt_version"),
            model_name=hydrated_ai.get("model_name"),
            category_scores=category_scores,
            missing_stages=missing_stages,
            remediation_hints=hints,
            details=details,
        )

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        return await ensure_connected(self.db, database_id)

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
        return cls._normalize_ai_artifact(
            {
                "ai_summary": getattr(snapshot, "ai_summary", None),
                "ai_recommendations": cls._parse_snapshot_json(getattr(snapshot, "ai_recommendations", None)),
                "ai_risks": cls._parse_snapshot_json(getattr(snapshot, "ai_risks", None)),
                "ai_roadmap": cls._parse_snapshot_json(getattr(snapshot, "ai_roadmap", None)),
                "ai_confidence": getattr(snapshot, "ai_confidence", None),
                "prompt_id": getattr(snapshot, "prompt_id", None),
                "prompt_version": getattr(snapshot, "prompt_version", None),
                "model_name": getattr(snapshot, "model_name", None),
                "trace_id": getattr(snapshot, "trace_id", None),
                "execution_status": getattr(snapshot, "execution_status", None),
                "fallback_used": getattr(snapshot, "used_fallback", None),
                "retry_count": getattr(snapshot, "retry_count", None),
            },
            fallback=breakdown_fallback,
        )

    @staticmethod
    def _snapshot_details(snapshot: ReadinessSnapshot | None) -> dict[str, Any]:
        if snapshot is None:
            return {}
        return {
            "prompt_id": getattr(snapshot, "prompt_id", None),
            "prompt_version": getattr(snapshot, "prompt_version", None),
            "model_name": getattr(snapshot, "model_name", None),
            "ai_summary": getattr(snapshot, "ai_summary", None),
            "ai_confidence": getattr(snapshot, "ai_confidence", None),
            "kpi_cluster_count": getattr(snapshot, "kpi_cluster_count", None),
            "successful_cluster_count": getattr(snapshot, "successful_cluster_count", None),
            "failed_cluster_count": getattr(snapshot, "failed_cluster_count", None),
            "coverage_percentage": getattr(snapshot, "coverage_percentage", None),
        }

    async def _fetch_database_semantic(self, database_id: int) -> DatabaseSemantic | None:
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        return result.scalars().first()

    async def _fetch_governance_packages(self, database_id: int) -> list[GovernancePackage]:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.database_id == database_id)
        )
        return list(result.scalars().all())

    async def _fetch_semantic_package(self, database_id: int) -> SemanticPackage | None:
        result = await self.db.execute(
            select(SemanticPackage).where(SemanticPackage.database_id == database_id)
        )
        return result.scalars().first()

    async def _fetch_relationship_packages(self, database_id: int) -> list[RelationshipPackage]:
        result = await self.db.execute(
            select(RelationshipPackage).where(RelationshipPackage.database_id == database_id)
        )
        return list(result.scalars().all())

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

    async def _collect_stats(self, database_id: int, context: IntelligenceContext | None = None) -> dict[str, Any]:
        snapshot = None
        database = await self._fetch_database(database_id)
        governance_packages = list(context.governance.packages) if context and context.governance and context.governance.packages else await self._fetch_governance_packages(database_id)
        semantic_package = context.semantics.package if context and context.semantics and context.semantics.package else await self._fetch_semantic_package(database_id)
        relationship_packages = list(context.relationships.packages) if context and context.relationships and context.relationships.packages else await self._fetch_relationship_packages(database_id)
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
        prompt_studio_templates = [
            PromptStudioService._template_id_for(member.value)
            for member in PromptStudioService._artifact_order()
        ]
        if tables > 0:
            try:
                prompt_context = context.prompts.package if context and context.prompts and context.prompts.package else await PromptStudioService(self.db)._build_context(database_id, context=context)
                for template_id in prompt_studio_templates:
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
            "semantic_package_present": semantic_package is not None,
            "semantic_package_domain": semantic_package.business_domain if semantic_package else None,
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
            "semantic_package_coverage": 100 if semantic_package else 0,
        }

        relationship_stats = {
            "graph_edges": int(graph_edge_count),
            "graph_table_coverage": self._ratio_score(len(graph_table_ids), int(tables)),
            "graph_density": self._relationship_density(int(graph_edge_count), int(tables)),
            "graph_cycles": int(graph_cycles),
            "relationship_intelligence": int(relationship_ai_rows),
            "isolated_tables": max(0, int(tables) - len(graph_table_ids)),
            "graph_table_ids": len(graph_table_ids),
            "relationship_packages": len(relationship_packages),
            "relationship_package_coverage": self._ratio_score(len(relationship_packages), max(1, int(tables) or 1)),
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
            "governance_packages": len(governance_packages),
            "governance_package_coverage": self._ratio_score(len(governance_packages), max(1, int(tables) or 1)),
        }

        kpi_count = 0
        kpi_artifacts = 0
        kpi_artifact_fresh = False
        kpi_confidence = 0.0
        kpi_cluster_count = 0
        successful_cluster_count = 0
        failed_cluster_count = 0
        coverage_percentage = 0.0
        if package_is_enabled("kpi"):
            try:
                kpi_rows = await self.db.execute(
                    select(
                        KPIIntelligence.cluster_id,
                        KPIIntelligence.execution_status,
                    )
                    .select_from(KPIIntelligence)
                    .where(KPIIntelligence.database_id == database_id)
                )
                rows = kpi_rows.all()
                kpi_count = len(rows)
                cluster_ids = {row[0] for row in rows if row[0] is not None}
                kpi_cluster_count = len(cluster_ids)
                successful_cluster_count = len(
                    {row[0] for row in rows if row[0] is not None and str(row[1] or "").lower() == "success"}
                )
                failed_cluster_count = len(
                    {row[0] for row in rows if row[0] is not None and str(row[1] or "").lower() not in {"success", ""}}
                )
                if kpi_cluster_count == 0:
                    kpi_cluster_count = successful_cluster_count + failed_cluster_count
                coverage_percentage = round(
                    (successful_cluster_count / max(1, kpi_cluster_count)) * 100.0,
                    2,
                ) if kpi_cluster_count > 0 else 0.0
                kpi_artifacts = int(
                    await self.db.scalar(
                        select(func.count())
                        .select_from(KPIArtifact)
                        .where(KPIArtifact.database_id == database_id)
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
                avg_kpi_confidence = await self.db.scalar(
                    select(func.avg(KPIIntelligence.confidence))
                    .select_from(KPIIntelligence)
                    .where(KPIIntelligence.database_id == database_id)
                )
                kpi_confidence = float(avg_kpi_confidence or 0.0)
            except Exception:
                logger.exception(error_message("failed to collect kpi readiness stats", database_id=database_id))

        kpi_stats = {
            "enabled": package_is_enabled("kpi"),
            "kpi_count": kpi_count,
            "artifact_count": kpi_artifacts,
            "artifact_fresh": kpi_artifact_fresh,
            "coverage_score": self._ratio_score(kpi_count, max(1, int(columns) // 10 or 1)),
            "confidence_score": kpi_confidence,
            "kpi_cluster_count": kpi_cluster_count,
            "successful_cluster_count": successful_cluster_count,
            "failed_cluster_count": failed_cluster_count,
            "coverage_percentage": coverage_percentage,
        }

        governance_complete = bool(columns > 0 and int(column_semantics) >= int(columns))
        prompt_protection_enabled = bool(
            settings.pii_prompt_protection_enabled
            and governance_complete
        )
        embedding_protection_enabled = bool(
            settings.pii_embedding_protection_enabled
            and governance_complete
            and int(embedding_status.get("completed_tables", 0)) > 0
        )
        governance_stats["governance_complete"] = governance_complete
        governance_stats["prompt_protection_enabled"] = prompt_protection_enabled
        governance_stats["embedding_protection_enabled"] = embedding_protection_enabled

        ai_context_stats = {
            "prompt_artifacts_rendered": prompt_artifacts_rendered,
            "prompt_artifacts_expected": len(prompt_studio_templates) + len(readiness_prompt_names),
            "prompt_context_length": prompt_context_length,
            "prompt_artifact_errors": prompt_artifact_errors,
            "embedding_coverage": self._ratio_score(int(embedding_status.get("completed_tables", 0)), int(max(1, tables))),
            "semantic_dependency_coverage": semantic_stats["semantic_table_coverage"],
            "package_coverage": self._ratio_score(
                int(bool(governance_packages)) + int(bool(semantic_package)) + int(bool(relationship_packages)),
                3,
            ),
        }

        package_completeness = self._package_completeness(
            {
                "governance_packages": len(governance_packages),
                "semantic_package_present": semantic_package is not None,
                "relationship_packages": len(relationship_packages),
                "kpi_cluster_count": kpi_cluster_count,
                "prompt_artifacts_rendered": prompt_artifacts_rendered,
                "embeddings": embedding_status,
                "readiness_snapshots": 1 if snapshot is not None else 0,
            }
        )

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
                    "prompt_protection_enabled": prompt_protection_enabled,
                    "embedding_protection_enabled": embedding_protection_enabled,
                },
                "package_completeness": package_completeness,
            }
            for template_id in readiness_prompt_names:
                try:
                    category, prompt_id = template_id.split("/", 1)
                    rendered = self.registry.render_prompt(prompt_id, readiness_context, category=category)
                    if rendered.user_prompt.strip():
                        prompt_artifacts_rendered += 1
                except Exception as exc:
                    prompt_artifact_errors.append(f"{template_id}: {exc}")
            ai_context_stats["prompt_artifacts_rendered"] = prompt_artifacts_rendered

        return {
            "metadata": metadata_stats,
            "semantic": semantic_stats,
            "relationships": relationship_stats,
            "relationship_intelligence": int(relationship_ai_rows),
            "ai_context": ai_context_stats,
            "package_completeness": package_completeness,
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
                "completeness": breakdown.details.get("package_completeness", {}),
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
                    "response_format": {"type": "json_object"},
                    "response_format": {"type": "json_object"},
                },
                completeness_score=breakdown.metadata_readiness_score / 100.0,
                coverage_score=breakdown.ai_context_readiness_score / 100.0,
                confidence_score=breakdown.overall_score / 100.0,
                execution_status="success",
                retry_count=0,
                fallback_used=False,
                extra_metadata={
                    "database_id": database.id,
                    "job_id": None,
                    "stage": "readiness",
                    "module": "ai_readiness",
                    "prompt_id": rendered.metadata.id,
                    "prompt_version": rendered.metadata.version,
                    "metadata_fingerprint": self._stage_metadata_fingerprint(database.id, rendered.metadata.id, rendered.metadata.version, breakdown.overall_score),
                },
            )
            parsed = self._parse_ai_assessment(ai_result.content or "")
            if not parsed:
                raise ValueError("empty_or_invalid_ai_response")
            normalized = self._normalize_ai_artifact(
                {
                    "ai_summary": parsed.get("executive_summary"),
                    "ai_recommendations": parsed.get("recommendations"),
                    "ai_risks": parsed.get("risks"),
                    "ai_roadmap": parsed.get("readiness_roadmap"),
                    "ai_confidence": parsed.get("confidence", 0.0),
                    "trace_id": getattr(ai_result, "trace_id", None),
                    "prompt_id": rendered.metadata.id,
                    "prompt_version": rendered.metadata.version,
                    "model_name": settings.azure_openai_deployment,
                    "token_metrics": getattr(ai_result, "token_usage", {}) or {},
                    "execution_status": "success",
                    "fallback_used": False,
                    "retry_count": 0,
                }
            )
            return {
                "ai_summary": normalized["ai_summary"] or "Readiness assessment generated.",
                "ai_recommendations": normalized["ai_recommendations"],
                "ai_risks": normalized["ai_risks"],
                "ai_roadmap": normalized["ai_roadmap"],
                "ai_confidence": normalized["ai_confidence"],
                "token_metrics": normalized["token_metrics"],
                "execution_status": normalized["execution_status"],
                "fallback_used": normalized["fallback_used"],
                "retry_count": normalized["retry_count"],
                "trace_id": normalized["trace_id"],
            }
        except Exception:
            logger.exception(error_message("ai readiness assessment generation failed", fallback="deterministic summary"))
            return {
                "ai_summary": self._fallback_ai_summary(breakdown),
                "ai_recommendations": self._fallback_recommendations(breakdown),
                "ai_risks": self._fallback_risks(breakdown),
                "ai_roadmap": self._fallback_roadmap(breakdown),
                "ai_confidence": round(min(1.0, breakdown.overall_score / 100.0), 3),
                "token_metrics": {},
                "execution_status": "fallback",
                "fallback_used": True,
                "retry_count": 0,
                "trace_id": None,
            }

    @staticmethod
    def _parse_ai_assessment(text: str) -> dict[str, Any]:
        payload = text.strip()
        if not payload:
            raise ValueError("empty_ai_response")
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
            f"operating with KPI coverage at {breakdown.coverage_percentage:.2f}% across "
            f"{breakdown.successful_cluster_count}/{max(1, breakdown.kpi_cluster_count)} successful clusters. "
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
        metadata = stats.get("metadata") or {}
        schemas = int(metadata.get("schemas", 0) or 0)
        tables = int(metadata.get("tables", 0) or 0)
        columns = int(metadata.get("columns", 0) or 0)

        if schemas <= 0 or tables <= 0 or columns <= 0:
            return 0

        schema_presence = 100
        table_presence = 100
        column_presence = 100
        schema_doc_coverage = self._ratio_score(int(metadata.get("schemas_with_description", 0) or 0), schemas)
        table_doc_coverage = self._ratio_score(int(metadata.get("tables_with_description", 0) or 0), tables)
        column_doc_coverage = self._ratio_score(int(metadata.get("columns_with_description", 0) or 0), columns)

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
        semantic = stats.get("semantic") or {}
        profile = semantic.get("profile") or {}
        tables = int((stats.get("metadata") or {}).get("tables", 0) or 0)
        if tables <= 0:
            return 0

        profile_completeness = self._presence_score(
            bool(profile.get("business_domain")),
            bool(profile.get("business_summary")),
            bool(profile.get("analysis_notes")),
            int(profile.get("key_entities", 0) or 0) > 0,
            int(profile.get("business_glossary", 0) or 0) > 0,
            int(profile.get("suggested_use_cases", 0) or 0) > 0,
        )
        semantic_table_coverage = int(semantic.get("semantic_table_coverage", 0) or 0)
        glossary_target = max(1, min(5, int(profile.get("key_entities", 0) or 5)))
        glossary_coverage = self._ratio_score(int(profile.get("business_glossary", 0) or 0), glossary_target)
        use_case_coverage = self._ratio_score(int(profile.get("suggested_use_cases", 0) or 0), 4)
        confidence = int(round(max(0.0, min(1.0, float(profile.get("confidence_score", 0.0) or 0.0))) * 100))
        package_coverage = semantic.get("semantic_package_coverage", 0)

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
                        + 0.05 * confidence
                        + 0.05 * package_coverage
                    )
                ),
            ),
        )

    def _relationship_score(self, stats: dict[str, Any]) -> int:
        metadata = stats.get("metadata") or {}
        raw_relationships = int(metadata.get("relationships", 0) or 0)
        tables = int(metadata.get("tables", 0) or 0)
        if tables <= 0:
            return 0
        if tables == 1:
            return 100

        relationship = stats.get("relationships") or {}
        package_coverage = relationship.get("relationship_package_coverage", 0)
        graph_edges = int(relationship.get("graph_edges", 0) or 0)
        relationship_coverage = self._ratio_score(graph_edges, max(1, raw_relationships))
        graph_table_coverage = int(relationship.get("graph_table_coverage", 0) or 0)
        density = min(100, int(round(float(relationship.get("graph_density", 0.0) or 0.0) * 100)))
        cycle_penalty = max(0, 100 - int(relationship.get("graph_cycles", 0) or 0) * 15)
        isolation_penalty = max(0, 100 - int(relationship.get("isolated_tables", 0) or 0) * 12)

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
                        + 0.05 * isolation_penalty
                        + 0.05 * package_coverage
                    )
                ),
            ),
        )

    def _ai_context_score(self, stats: dict[str, Any]) -> int:
        ai_context = stats.get("ai_context") or {}
        metadata = stats.get("metadata") or {}
        tables = int(metadata.get("tables", 0) or 0)
        if tables <= 0:
            return 0

        artifact_coverage = self._ratio_score(
            int(ai_context.get("prompt_artifacts_rendered", 0) or 0),
            int(ai_context.get("prompt_artifacts_expected", 0) or 0),
        )
        embedding_coverage = int(ai_context.get("embedding_coverage", 0) or 0)
        semantic_dependency_coverage = int(ai_context.get("semantic_dependency_coverage", 0) or 0)
        package_coverage = ai_context.get("package_coverage", 0)

        return max(
            0,
            min(
                100,
                int(
                    round(
                        0.50 * artifact_coverage
                        + 0.30 * embedding_coverage
                        + 0.20 * semantic_dependency_coverage
                        + 0.05 * package_coverage
                    )
                ),
            ),
        )

    def _governance_score(self, stats: dict[str, Any]) -> int:
        governance = stats.get("governance") or {}
        pii_identified = int(governance.get("pii_identified_coverage", 0) or 0)
        pii_classified = int(governance.get("pii_classified_coverage", 0) or 0)
        prompt_protection = 100 if governance.get("prompt_protection_enabled", False) else 0
        embedding_protection = 100 if governance.get("embedding_protection_enabled", False) else 0
        package_coverage = governance.get("governance_package_coverage", 0)

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
                        + 0.05 * package_coverage
                    )
                ),
            ),
        )

    def _kpi_score(self, stats: dict[str, Any]) -> int:
        kpi = stats["kpi"]
        package_coverage = max(
            int(stats["governance"].get("governance_package_coverage", 0) or 0),
            int(stats["semantic"].get("semantic_package_coverage", 0) or 0),
            int(stats["relationships"].get("relationship_package_coverage", 0) or 0),
        )
        rules = self._kpi_rules()
        if not kpi["enabled"] or kpi["kpi_count"] < int(rules.get("min_kpi_count", 1)):
            return min(package_coverage, 40)

        coverage = float(kpi.get("coverage_percentage", 0.0) or 0.0)
        if coverage <= 0:
            return 0
        if coverage < 25:
            return 10
        if coverage < 50:
            return 25
        if coverage < 75:
            return 55
        if coverage < 100:
            return 80

        confidence = max(0, min(100, int(round(float(kpi["confidence_score"]) * 100))))
        freshness = 100 if kpi["artifact_fresh"] else 0
        weights = rules.get("weights", {})
        return max(
            0,
            min(
                100,
                int(
                    round(
                        float(weights.get("coverage", 0.40)) * max(kpi["coverage_score"], coverage)
                        + float(weights.get("freshness", 0.35)) * freshness
                        + float(weights.get("confidence", 0.25)) * confidence
                        + 0.05 * package_coverage
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
            if not governance.get("governance_complete"):
                hints.append("Run metadata-driven governance classification for all columns.")
            elif not governance["prompt_protection_enabled"]:
                hints.append("Prompt protection is disabled or governance intelligence is incomplete.")
            if governance.get("governance_complete") and not governance["embedding_protection_enabled"]:
                hints.append("Complete embedding generation so PII masking can protect vector indexes.")

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
