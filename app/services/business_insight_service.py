"""Business insight generation from persisted intelligence packages."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.business_insight import BusinessInsight
from app.models.metadata import GovernancePackage, KPIIntelligence, RelationshipPackage, SemanticPackage
from app.services.ai_observability_service import AIObservabilityService


class BusinessInsightService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int) -> list[dict[str, Any]]:
        governance_packages = await self._fetch_governance_packages(database_id)
        semantic_package = await self._fetch_semantic_package(database_id)
        relationship_packages = await self._fetch_relationship_packages(database_id)
        kpi_rows = await self._fetch_kpis(database_id)
        deterministic = self._derive_insights(governance_packages, semantic_package, relationship_packages, kpi_rows)
        insights = await self._generate_with_ai(
            database_id=database_id,
            governance_packages=governance_packages,
            semantic_package=semantic_package,
            relationship_packages=relationship_packages,
            kpi_rows=kpi_rows,
            fallback=deterministic,
        )
        await self._persist(database_id, insights)
        return insights

    async def get_insights(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(BusinessInsight).where(BusinessInsight.database_id == database_id).order_by(BusinessInsight.confidence_score.desc())
        )
        rows = result.scalars().all()
        return {
            "database_id": database_id,
            "insights": [
                {
                    "id": row.id,
                    "insight_text": row.insight_text,
                    "confidence_score": row.confidence_score,
                    "impact_level": row.impact_level,
                    "evidence": json.loads(row.evidence or "[]"),
                    "trace_id": row.trace_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }

    def _derive_insights(
        self,
        governance_packages: list[GovernancePackage],
        semantic_package: SemanticPackage | None,
        relationship_packages: list[RelationshipPackage],
        kpi_rows: list[KPIIntelligence],
    ) -> list[dict[str, Any]]:
        insights: list[dict[str, Any]] = []
        relationship_texts = self._relationship_texts(relationship_packages)
        event_texts = self._event_texts(governance_packages, relationship_packages)
        kpi_texts = self._kpi_texts(kpi_rows)

        if relationship_texts:
            first = relationship_texts[0]
            insights.append(
                {
                    "insight_text": first,
                    "confidence_score": 0.86,
                    "impact_level": "high",
                    "evidence": [
                        {"source": "relationships", "count": len(relationship_packages)},
                        {"source": "semantic", "business_domain": semantic_package.business_domain if semantic_package else None},
                    ],
                    "trace_id": self._first_trace_id(relationship_packages, semantic_package),
                }
            )
        if event_texts:
            insights.append(
                {
                    "insight_text": event_texts[0],
                    "confidence_score": 0.84,
                    "impact_level": "high",
                    "evidence": [
                        {"source": "governance", "packages": len(governance_packages)},
                        {"source": "kpi", "count": len(kpi_rows)},
                    ],
                    "trace_id": self._first_trace_id(relationship_packages, semantic_package),
                }
            )
        if relationship_packages:
            cluster_sizes = [len(package.entity_graph or []) for package in relationship_packages]
            largest = max(cluster_sizes or [0])
            insights.append(
                {
                    "insight_text": f"Relationship intelligence covers {len(relationship_packages)} cluster(s) with a largest graph size of {largest}.",
                    "confidence_score": 0.72 if largest else 0.55,
                    "impact_level": "medium" if largest else "low",
                    "evidence": [
                        {"source": "relationships", "cluster_count": len(relationship_packages)},
                        {"source": "graph", "largest_cluster_size": largest},
                    ],
                    "trace_id": self._first_trace_id(relationship_packages, semantic_package),
                }
            )
        if semantic_package and semantic_package.semantic_summary:
            insights.append(
                {
                    "insight_text": semantic_package.semantic_summary,
                    "confidence_score": float(semantic_package.confidence_score or 0.0),
                    "impact_level": "medium",
                    "evidence": [{"source": "semantic", "business_domain": semantic_package.business_domain}],
                    "trace_id": semantic_package.trace_id,
                }
            )
        if kpi_texts:
            kpi = kpi_rows[0]
            insights.append(
                {
                    "insight_text": kpi_texts[0],
                    "confidence_score": float(kpi.confidence_score or kpi.confidence or 0.0),
                    "impact_level": "medium",
                    "evidence": [{"source": "kpi", "formula": kpi.formula, "cluster": kpi.cluster_name}],
                    "trace_id": kpi.trace_id,
                }
            )
        return insights[:10]

    async def _generate_with_ai(
        self,
        *,
        database_id: int,
        governance_packages: list[GovernancePackage],
        semantic_package: SemanticPackage | None,
        relationship_packages: list[RelationshipPackage],
        kpi_rows: list[KPIIntelligence],
        fallback: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            rendered = self.registry.render_prompt(
                "business_insight_generation",
                {
                    "database_context": {"database_id": database_id},
                    "governance_package": [self._governance_row(pkg) for pkg in governance_packages],
                    "semantic_package": self._semantic_row(semantic_package) if semantic_package else {},
                    "relationship_package": [self._relationship_row(pkg) for pkg in relationship_packages],
                    "kpi_package": [self._kpi_row(row) for row in kpi_rows],
                    "graph_features": {
                        "cluster_count": len(relationship_packages),
                        "relationship_count": sum(len(pkg.entity_graph or []) for pkg in relationship_packages),
                    },
                    "insights": fallback,
                },
                category="insights",
            )
            result = await AIObservabilityService().generate(
                operation="chat",
                module="business_insights",
                artifact_type="business_insight_generation",
                prompt_id=rendered.metadata.id,
                prompt_version=rendered.metadata.version,
                model_name=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": rendered.system_message or "You are a business insight generation engine."},
                    {"role": "user", "content": rendered.user_prompt},
                ],
                request_kwargs={"response_format": {"type": "json_object"}},
                completeness_score=0.0,
                coverage_score=0.0,
                confidence_score=0.0,
                execution_status="success",
                fallback_used=False,
                retry_count=0,
                extra_metadata={"feature": "business_insights"},
            )
            payload = json.loads(result.content or "{}")
            insights = payload.get("insights")
            if isinstance(insights, list) and insights:
                return insights
        except Exception:
            pass
        return fallback[:10]

    def _relationship_texts(self, relationship_packages: list[RelationshipPackage]) -> list[str]:
        texts: list[str] = []
        for package in relationship_packages:
            for rel in package.entity_graph[:10]:
                source = rel.get("source_table_name") or rel.get("source") or rel.get("from") or "source"
                target = rel.get("target_table_name") or rel.get("target") or rel.get("to") or "target"
                texts.append(f"{source} depends on {target}.")
            for flow in package.lifecycle_flows[:10]:
                if isinstance(flow, dict):
                    source = flow.get("source") or flow.get("from") or "source"
                    target = flow.get("target") or flow.get("to") or "target"
                    texts.append(f"{source} flows into {target}.")
        return texts

    def _event_texts(self, governance_packages: list[GovernancePackage], relationship_packages: list[RelationshipPackage]) -> list[str]:
        texts: list[str] = []
        tables = [pkg.table_name for pkg in governance_packages if pkg.table_name]
        if tables:
            primary = tables[0]
            texts.append(f"{primary} is a key operational table in the current intelligence package.")
        if len(tables) > 1:
            texts.append(f"{tables[0]} and {tables[1]} participate in the same business process context.")
        if not texts and relationship_packages:
            texts.append("Business activity is coordinated across the detected relationship clusters.")
        return texts

    def _kpi_texts(self, kpi_rows: list[KPIIntelligence]) -> list[str]:
        texts: list[str] = []
        for kpi in kpi_rows[:3]:
            name = kpi.name or "KPI"
            formula = kpi.formula or "n/a"
            texts.append(f"{name} is tracked using the formula {formula}.")
        return texts

    @staticmethod
    def _governance_row(pkg: GovernancePackage) -> dict[str, Any]:
        return {
            "table_name": pkg.table_name,
            "schema_name": pkg.schema_name,
            "table_summary": pkg.table_summary,
            "business_purpose": pkg.business_purpose,
            "confidence_score": pkg.confidence_score,
        }

    @staticmethod
    def _semantic_row(pkg: SemanticPackage | None) -> dict[str, Any]:
        if not pkg:
            return {}
        return {
            "business_domain": pkg.business_domain,
            "semantic_summary": pkg.semantic_summary,
            "business_entities": pkg.business_entities,
            "business_processes": pkg.business_processes,
            "business_capabilities": pkg.business_capabilities,
            "confidence_score": pkg.confidence_score,
        }

    @staticmethod
    def _relationship_row(pkg: RelationshipPackage) -> dict[str, Any]:
        return {
            "cluster_id": pkg.cluster_id,
            "domain_name": pkg.domain_name,
            "cluster_summary": pkg.cluster_summary,
            "entity_graph": pkg.entity_graph,
            "lifecycle_flows": pkg.lifecycle_flows,
            "confidence_score": pkg.confidence_score,
        }

    @staticmethod
    def _kpi_row(row: KPIIntelligence) -> dict[str, Any]:
        return {
            "name": row.name,
            "description": row.description,
            "formula": row.formula,
            "confidence": row.confidence_score or row.confidence,
            "cluster_name": row.cluster_name,
            "trace_id": row.trace_id,
        }

    async def _persist(self, database_id: int, insights: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(BusinessInsight).where(BusinessInsight.database_id == database_id))
        for insight in insights:
            self.db.add(
                BusinessInsight(
                    database_id=database_id,
                    insight_text=insight["insight_text"],
                    confidence_score=float(insight.get("confidence_score", 0.0)),
                    impact_level=insight.get("impact_level"),
                    evidence=json.dumps(insight.get("evidence", []), default=str),
                    trace_id=insight.get("trace_id"),
                )
            )
        await self.db.flush()

    @staticmethod
    def _first_trace_id(relationship_packages: list[RelationshipPackage], semantic_package: SemanticPackage | None) -> str | None:
        if semantic_package and semantic_package.trace_id:
            return semantic_package.trace_id
        for package in relationship_packages:
            if package.trace_id:
                return package.trace_id
        return None

    async def _fetch_governance_packages(self, database_id: int) -> list[GovernancePackage]:
        result = await self.db.execute(select(GovernancePackage).where(GovernancePackage.database_id == database_id))
        return list(result.scalars().all())

    async def _fetch_semantic_package(self, database_id: int) -> SemanticPackage | None:
        result = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        return result.scalars().first()

    async def _fetch_relationship_packages(self, database_id: int) -> list[RelationshipPackage]:
        result = await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))
        return list(result.scalars().all())

    async def _fetch_kpis(self, database_id: int) -> list[KPIIntelligence]:
        result = await self.db.execute(select(KPIIntelligence).where(KPIIntelligence.database_id == database_id))
        return list(result.scalars().all())
