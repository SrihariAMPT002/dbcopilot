"""Warehouse design discovery."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.metadata import RelationshipPackage, SemanticPackage
from app.models.warehouse_design import WarehouseDesign
from app.services.ai_observability_service import AIObservabilityService
from app.services.relationship_package_mapper import relationship_package_to_dto


class WarehouseDesignService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int) -> list[dict[str, Any]]:
        semantic = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        relationship = await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))
        payload = {"semantic": self._semantic_row(semantic.scalars().first()), "relationships": [self._relationship_row(pkg) for pkg in relationship.scalars().all()]}
        deterministic = self._deterministic(payload)
        rows = await self._ai_enrich(database_id, payload, deterministic)
        await self._persist(database_id, rows)
        return rows

    async def get_designs(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(WarehouseDesign).where(WarehouseDesign.database_id == database_id).order_by(WarehouseDesign.confidence_score.desc()))
        rows = result.scalars().all()
        return {"database_id": database_id, "warehouse_designs": [self._row(row) for row in rows]}

    def _deterministic(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        semantic = payload["semantic"]
        entities = semantic.get("business_entities") or []
        design: list[dict[str, Any]] = []
        if entities:
            design.append({"design_name": "Star schema", "design_type": "star_schema", "description": "Candidate dimensional model around detected business entities.", "confidence_score": 0.66, "evidence": [{"entities": entities[:5]}]})
        if payload["relationships"]:
            design.append({"design_name": "Snowflake variant", "design_type": "snowflake_schema", "description": "Extended warehouse design derived from relationship topology.", "confidence_score": 0.61, "evidence": [{"clusters": len(payload["relationships"])}]})
        return design[:10]

    async def _ai_enrich(self, database_id: int, payload: dict[str, Any], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            rendered = self.registry.render_prompt("warehouse_design_discovery", {"database_id": database_id, **payload, "warehouse_designs": fallback}, category="warehouse")
            result = await AIObservabilityService().generate(operation="chat", module="warehouse_designs", artifact_type="warehouse_design_discovery", prompt_id=rendered.metadata.id, prompt_version=rendered.metadata.version, model_name=settings.azure_openai_deployment, messages=[{"role": "system", "content": rendered.system_message or "You are a warehouse design engine."}, {"role": "user", "content": rendered.user_prompt}], request_kwargs={"response_format": {"type": "json_object"}}, completeness_score=0.0, coverage_score=0.0, confidence_score=0.0, execution_status="success", fallback_used=False, retry_count=0, extra_metadata={"feature": "warehouse_designs"})
            parsed = json.loads(result.content or "{}")
            rows = parsed.get("warehouse_designs")
            if isinstance(rows, list) and rows:
                return rows
        except Exception:
            pass
        return fallback

    async def _persist(self, database_id: int, rows: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(WarehouseDesign).where(WarehouseDesign.database_id == database_id))
        for row in rows:
            self.db.add(WarehouseDesign(database_id=database_id, design_name=row["design_name"], design_type=row.get("design_type"), description=row.get("description"), confidence_score=float(row.get("confidence_score", 0.0)), evidence=json.dumps(row.get("evidence", []), default=str), trace_id=row.get("trace_id")))
        await self.db.flush()

    @staticmethod
    def _row(row: WarehouseDesign) -> dict[str, Any]:
        return {"id": row.id, "design_name": row.design_name, "design_type": row.design_type, "description": row.description, "confidence_score": row.confidence_score, "evidence": json.loads(row.evidence or "[]"), "trace_id": row.trace_id, "created_at": row.created_at.isoformat() if row.created_at else None}

    @staticmethod
    def _semantic_row(pkg: SemanticPackage | None) -> dict[str, Any]:
        if not pkg:
            return {}
        return {"business_domain": pkg.business_domain, "business_entities": pkg.business_entities, "business_processes": pkg.business_processes}

    @staticmethod
    def _relationship_row(pkg: RelationshipPackage) -> dict[str, Any]:
        dto = relationship_package_to_dto(pkg)
        return {"cluster_id": dto.cluster_id, "entity_graph": dto.entity_graph, "lifecycle_flows": dto.lifecycle_flows}
