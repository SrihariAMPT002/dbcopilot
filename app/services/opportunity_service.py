"""Opportunity recommendation generation."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.data_product import DataProduct
from app.models.metadata import GovernancePackage, KPIIntelligence, RelationshipPackage, SemanticPackage
from app.models.opportunity_recommendation import OpportunityRecommendation
from app.models.readiness_snapshot import ReadinessSnapshot
from app.services.ai_observability_service import AIObservabilityService
from app.services.relationship_package_mapper import relationship_package_to_dto


class OpportunityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int) -> list[dict[str, Any]]:
        payload = await self._build_payload(database_id)
        deterministic = self._deterministic(payload)
        ai_rows = await self._ai_enrich(database_id, payload, deterministic)
        await self._persist(database_id, ai_rows)
        return ai_rows

    async def get_opportunities(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(OpportunityRecommendation).where(OpportunityRecommendation.database_id == database_id).order_by(OpportunityRecommendation.confidence_score.desc())
        )
        rows = result.scalars().all()
        return {"database_id": database_id, "opportunities": [self._row(row) for row in rows]}

    async def _build_payload(self, database_id: int) -> dict[str, Any]:
        governance = await self.db.execute(select(GovernancePackage).where(GovernancePackage.database_id == database_id))
        semantic = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        relationship = await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))
        relationship_rows = [relationship_package_to_dto(pkg) for pkg in relationship.scalars().all()]
        kpis = await self.db.execute(select(KPIIntelligence).where(KPIIntelligence.database_id == database_id))
        readiness = await self.db.execute(select(ReadinessSnapshot).where(ReadinessSnapshot.database_id == database_id))
        return {
            "governance": [self._governance_row(pkg) for pkg in governance.scalars().all()],
            "semantic": self._semantic_row(semantic.scalars().first()),
            "relationships": [self._relationship_row(pkg) for pkg in relationship_rows],
            "kpis": [self._kpi_row(row) for row in kpis.scalars().all()],
            "readiness": self._readiness_row(readiness.scalars().first()),
        }

    def _deterministic(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        opportunities: list[dict[str, Any]] = []
        if payload["relationships"]:
            opportunities.append({
                "recommendation_text": "Review missing dimensional context for the busiest relationship clusters.",
                "recommendation_type": "dimension_gap",
                "confidence_score": 0.72,
                "evidence": [{"relationships": len(payload["relationships"])}],
            })
        if payload["kpis"]:
            opportunities.append({
                "recommendation_text": "Expand KPI coverage around the strongest persisted KPI package.",
                "recommendation_type": "kpi_gap",
                "confidence_score": 0.68,
                "evidence": [{"kpis": len(payload["kpis"])}],
            })
        if payload["readiness"] and payload["readiness"]["overall_score"] < 70:
            opportunities.append({
                "recommendation_text": "Raise readiness coverage before exposing this database to downstream agents.",
                "recommendation_type": "readiness_gap",
                "confidence_score": 0.8,
                "evidence": [payload["readiness"]],
            })
        return opportunities[:10]

    async def _ai_enrich(self, database_id: int, payload: dict[str, Any], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            rendered = self.registry.render_prompt("opportunity_discovery", {"database_id": database_id, **payload, "opportunities": fallback}, category="opportunity")
            result = await AIObservabilityService().generate(
                operation="chat",
                module="opportunities",
                artifact_type="opportunity_discovery",
                prompt_id=rendered.metadata.id,
                prompt_version=rendered.metadata.version,
                model_name=settings.azure_openai_deployment,
                messages=[{"role": "system", "content": rendered.system_message or "You are an opportunity discovery engine."}, {"role": "user", "content": rendered.user_prompt}],
                request_kwargs={"response_format": {"type": "json_object"}},
                completeness_score=0.0,
                coverage_score=0.0,
                confidence_score=0.0,
                execution_status="success",
                fallback_used=False,
                retry_count=0,
                extra_metadata={"feature": "opportunities"},
            )
            parsed = json.loads(result.content or "{}")
            rows = parsed.get("opportunities")
            if isinstance(rows, list) and rows:
                return rows
        except Exception:
            pass
        return fallback

    async def _persist(self, database_id: int, rows: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(OpportunityRecommendation).where(OpportunityRecommendation.database_id == database_id))
        for row in rows:
            self.db.add(OpportunityRecommendation(database_id=database_id, recommendation_text=row["recommendation_text"], recommendation_type=row.get("recommendation_type"), confidence_score=float(row.get("confidence_score", 0.0)), evidence=json.dumps(row.get("evidence", []), default=str), trace_id=row.get("trace_id")))
        await self.db.flush()

    @staticmethod
    def _row(row: OpportunityRecommendation) -> dict[str, Any]:
        return {"id": row.id, "recommendation_text": row.recommendation_text, "recommendation_type": row.recommendation_type, "confidence_score": row.confidence_score, "evidence": json.loads(row.evidence or "[]"), "trace_id": row.trace_id, "created_at": row.created_at.isoformat() if row.created_at else None}

    @staticmethod
    def _governance_row(pkg: GovernancePackage) -> dict[str, Any]:
        return {"table_name": pkg.table_name, "schema_name": pkg.schema_name, "confidence_score": pkg.confidence_score}

    @staticmethod
    def _semantic_row(pkg: SemanticPackage | None) -> dict[str, Any]:
        if not pkg:
            return {}
        return {"business_domain": pkg.business_domain, "business_entities": pkg.business_entities, "business_processes": pkg.business_processes, "confidence_score": pkg.confidence_score}

    @staticmethod
    def _relationship_row(pkg: Any) -> dict[str, Any]:
        dto = relationship_package_to_dto(pkg)
        entity_graph = getattr(dto, "entity_graph", None) or []
        lifecycle_flows = getattr(dto, "lifecycle_flows", None) or []
        return {
            "cluster_id": getattr(dto, "cluster_id", None),
            "domain_name": getattr(dto, "domain_name", None),
            "confidence_score": float(getattr(dto, "confidence_score", 0.0) or 0.0),
            "entity_graph": entity_graph,
            "lifecycle_flows": lifecycle_flows,
            "cluster_summary": getattr(dto, "cluster_summary", None),
            "source_table_name": getattr(dto, "source_table_name", None),
            "target_table_name": getattr(dto, "target_table_name", None),
        }

    @staticmethod
    def _kpi_row(row: KPIIntelligence) -> dict[str, Any]:
        return {"name": row.name, "formula": row.formula, "confidence_score": row.confidence_score}

    @staticmethod
    def _readiness_row(row: ReadinessSnapshot | None) -> dict[str, Any]:
        if not row:
            return {}
        return {"overall_score": row.overall_score, "governance_score": row.governance_readiness_score, "semantic_score": row.semantic_readiness_score, "relationship_score": row.relationship_readiness_score, "kpi_score": row.kpi_readiness_score}
