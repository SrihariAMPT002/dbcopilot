"""Predictive readiness scoring."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.agent_capability import AgentCapability
from app.models.metadata import GovernancePackage, RelationshipPackage, SemanticPackage
from app.models.predictive_readiness import PredictiveReadiness
from app.services.ai_observability_service import AIObservabilityService


class PredictiveReadinessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int) -> dict[str, Any]:
        governance = await self.db.execute(select(GovernancePackage).where(GovernancePackage.database_id == database_id))
        semantic = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        relationship = await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))
        payload = {"governance": [self._governance_row(pkg) for pkg in governance.scalars().all()], "semantic": self._semantic_row(semantic.scalars().first()), "relationships": [self._relationship_row(pkg) for pkg in relationship.scalars().all()]}
        deterministic = self._deterministic(payload)
        row = await self._ai_enrich(database_id, payload, deterministic)
        await self._persist(database_id, row)
        return row

    async def get_predictive_readiness(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(PredictiveReadiness).where(PredictiveReadiness.database_id == database_id).order_by(PredictiveReadiness.created_at.desc()))
        row = result.scalars().first()
        if not row:
            return {"database_id": database_id, "predictive_readiness": None}
        return self._row(row)

    def _deterministic(self, payload: dict[str, Any]) -> dict[str, Any]:
        governance = len(payload["governance"])
        relationships = len(payload["relationships"])
        semantic = payload["semantic"]
        agent_score = min(0.95, 0.35 + governance * 0.05 + relationships * 0.04 + (0.1 if semantic else 0.0))
        return {
            "agent_readiness_score": round(agent_score, 2),
            "text_to_sql_score": round(min(0.95, agent_score + 0.05), 2),
            "rag_score": round(min(0.95, agent_score + 0.03), 2),
            "analytics_score": round(min(0.95, agent_score + 0.02), 2),
            "forecasting_score": round(min(0.95, agent_score - 0.02), 2),
            "anomaly_detection_score": round(min(0.95, agent_score - 0.01), 2),
            "ml_score": round(min(0.95, agent_score - 0.04), 2),
            "agent_capabilities": [{"capability_name": "text_to_sql", "score": round(min(0.95, agent_score + 0.05), 2)}],
            "evidence": [{"governance_packages": governance, "relationships": relationships}],
        }

    async def _ai_enrich(self, database_id: int, payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            rendered = self.registry.render_prompt("predictive_readiness_assessment", {"database_id": database_id, **payload, "predictive_readiness": fallback}, category="predictive")
            result = await AIObservabilityService().generate(operation="chat", module="predictive_readiness", artifact_type="predictive_readiness_assessment", prompt_id=rendered.metadata.id, prompt_version=rendered.metadata.version, model_name=settings.azure_openai_deployment, messages=[{"role": "system", "content": rendered.system_message or "You are a predictive readiness engine."}, {"role": "user", "content": rendered.user_prompt}], request_kwargs={"max_completion_tokens": 6000, "response_format": {"type": "json_object"}}, completeness_score=0.0, coverage_score=0.0, confidence_score=0.0, execution_status="success", fallback_used=False, retry_count=0, extra_metadata={"feature": "predictive_readiness"})
            parsed = json.loads(result.content or "{}")
            if parsed:
                return parsed
        except Exception:
            pass
        return fallback

    async def _persist(self, database_id: int, payload: dict[str, Any]) -> None:
        await self.db.execute(delete(PredictiveReadiness).where(PredictiveReadiness.database_id == database_id))
        self.db.add(PredictiveReadiness(database_id=database_id, agent_readiness_score=float(payload.get("agent_readiness_score", 0.0)), text_to_sql_score=float(payload.get("text_to_sql_score", 0.0)), rag_score=float(payload.get("rag_score", 0.0)), analytics_score=float(payload.get("analytics_score", 0.0)), forecasting_score=float(payload.get("forecasting_score", 0.0)), anomaly_detection_score=float(payload.get("anomaly_detection_score", 0.0)), ml_score=float(payload.get("ml_score", 0.0)), agent_capabilities=json.dumps(payload.get("agent_capabilities", []), default=str), evidence=json.dumps(payload.get("evidence", []), default=str), trace_id=payload.get("trace_id")))
        await self.db.execute(delete(AgentCapability).where(AgentCapability.database_id == database_id))
        for cap in payload.get("agent_capabilities", []):
            self.db.add(AgentCapability(database_id=database_id, capability_name=str(cap.get("capability_name") or cap.get("name") or "capability"), capability_type=cap.get("capability_type"), score=float(cap.get("score", 0.0)), evidence=json.dumps(cap.get("evidence", []), default=str), trace_id=cap.get("trace_id")))
        await self.db.flush()

    def _row(self, row: PredictiveReadiness) -> dict[str, Any]:
        return {"id": row.id, "database_id": row.database_id, "agent_readiness_score": row.agent_readiness_score, "text_to_sql_score": row.text_to_sql_score, "rag_score": row.rag_score, "analytics_score": row.analytics_score, "forecasting_score": row.forecasting_score, "anomaly_detection_score": row.anomaly_detection_score, "ml_score": row.ml_score, "agent_capabilities": json.loads(row.agent_capabilities or "[]"), "evidence": json.loads(row.evidence or "[]"), "trace_id": row.trace_id, "created_at": row.created_at.isoformat() if row.created_at else None}

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
        return {"cluster_id": pkg.cluster_id, "cluster_confidence": pkg.cluster_confidence}
