"""Recommendation engine."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.metadata import GovernancePackage, RelationshipPackage, SemanticPackage
from app.models.recommendation import Recommendation
from app.models.readiness_snapshot import ReadinessSnapshot
from app.services.ai_observability_service import AIObservabilityService
from app.services.relationship_package_mapper import relationship_package_to_dto


class RecommendationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int) -> list[dict[str, Any]]:
        governance = await self.db.execute(select(GovernancePackage).where(GovernancePackage.database_id == database_id))
        semantic = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        relationship = await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))
        readiness = await self.db.execute(select(ReadinessSnapshot).where(ReadinessSnapshot.database_id == database_id))
        payload = {"governance": [self._governance_row(pkg) for pkg in governance.scalars().all()], "semantic": self._semantic_row(semantic.scalars().first()), "relationships": [self._relationship_row(pkg) for pkg in relationship.scalars().all()], "readiness": self._readiness_row(readiness.scalars().first())}
        deterministic = self._deterministic(payload)
        rows = await self._ai_enrich(database_id, payload, deterministic)
        await self._persist(database_id, rows)
        return rows

    async def get_recommendations(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(Recommendation).where(Recommendation.database_id == database_id).order_by(Recommendation.confidence_score.desc()))
        rows = result.scalars().all()
        return {"database_id": database_id, "recommendations": [self._row(row) for row in rows]}

    def _deterministic(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if payload["governance"]:
            rows.append({"recommendation_text": "Prioritize governance coverage on tables with the strongest PII evidence.", "recommendation_type": "governance", "priority": "high", "confidence_score": 0.69, "evidence": [{"tables": len(payload["governance"])}]})
        if payload["relationships"]:
            rows.append({"recommendation_text": "Add indexing or join support for frequently related tables.", "recommendation_type": "performance", "priority": "medium", "confidence_score": 0.63, "evidence": [{"clusters": len(payload["relationships"])}]})
        if payload["readiness"] and payload["readiness"]["overall_score"] < 70:
            rows.append({"recommendation_text": "Improve readiness before enabling agent workflows.", "recommendation_type": "readiness", "priority": "high", "confidence_score": 0.79, "evidence": [payload["readiness"]]})
        return rows[:10]

    async def _ai_enrich(self, database_id: int, payload: dict[str, Any], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            rendered = self.registry.render_prompt("recommendation_generation", {"database_id": database_id, **payload, "recommendations": fallback}, category="recommendations")
            result = await AIObservabilityService().generate(operation="chat", module="recommendations", artifact_type="recommendation_generation", prompt_id=rendered.metadata.id, prompt_version=rendered.metadata.version, model_name=settings.azure_openai_deployment, messages=[{"role": "system", "content": rendered.system_message or "You are a recommendation engine."}, {"role": "user", "content": rendered.user_prompt}], request_kwargs={"response_format": {"type": "json_object"}}, completeness_score=0.0, coverage_score=0.0, confidence_score=0.0, execution_status="success", fallback_used=False, retry_count=0, extra_metadata={"feature": "recommendations"})
            parsed = json.loads(result.content or "{}")
            rows = parsed.get("recommendations")
            if isinstance(rows, list) and rows:
                return rows
        except Exception:
            pass
        return fallback

    async def _persist(self, database_id: int, rows: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(Recommendation).where(Recommendation.database_id == database_id))
        for row in rows:
            self.db.add(Recommendation(database_id=database_id, recommendation_text=row["recommendation_text"], recommendation_type=row.get("recommendation_type"), priority=row.get("priority"), confidence_score=float(row.get("confidence_score", 0.0)), evidence=json.dumps(row.get("evidence", []), default=str), trace_id=row.get("trace_id")))
        await self.db.flush()

    @staticmethod
    def _row(row: Recommendation) -> dict[str, Any]:
        return {"id": row.id, "recommendation_text": row.recommendation_text, "recommendation_type": row.recommendation_type, "priority": row.priority, "confidence_score": row.confidence_score, "evidence": json.loads(row.evidence or "[]"), "trace_id": row.trace_id, "created_at": row.created_at.isoformat() if row.created_at else None}

    @staticmethod
    def _governance_row(pkg: GovernancePackage) -> dict[str, Any]:
        return {"table_name": pkg.table_name, "confidence_score": pkg.confidence_score}

    @staticmethod
    def _semantic_row(pkg: SemanticPackage | None) -> dict[str, Any]:
        if not pkg:
            return {}
        return {"business_domain": pkg.business_domain, "business_entities": pkg.business_entities}

    @staticmethod
    def _relationship_row(pkg: RelationshipPackage) -> dict[str, Any]:
        dto = relationship_package_to_dto(pkg)
        return {"cluster_id": dto.cluster_id, "confidence_score": dto.confidence_score}

    @staticmethod
    def _readiness_row(row: ReadinessSnapshot | None) -> dict[str, Any]:
        if not row:
            return {}
        return {"overall_score": row.overall_score, "governance_score": row.governance_readiness_score, "semantic_score": row.semantic_readiness_score, "relationship_score": row.relationship_readiness_score, "kpi_score": row.kpi_readiness_score}
