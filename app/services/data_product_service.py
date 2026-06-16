"""Data product discovery."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.core.config import settings
from app.models.data_product import DataProduct
from app.models.metadata import RelationshipPackage, SemanticPackage
from app.services.ai_observability_service import AIObservabilityService


class DataProductService:
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

    async def get_products(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(DataProduct).where(DataProduct.database_id == database_id).order_by(DataProduct.confidence_score.desc()))
        rows = result.scalars().all()
        return {"database_id": database_id, "data_products": [self._row(row) for row in rows]}

    def _deterministic(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        semantic = payload["semantic"]
        products: list[dict[str, Any]] = []
        domain = semantic.get("business_domain") or "analytics"
        entities = semantic.get("business_entities") or []
        if entities:
            products.append({"product_name": f"{domain} 360", "product_type": "360_view", "description": f"Curated view for {domain} entities.", "confidence_score": 0.7, "evidence": [{"entities": entities[:5]}]})
        if payload["relationships"]:
            products.append({"product_name": f"{domain} Mart", "product_type": "mart", "description": "Curated analytics mart aligned to detected relationship clusters.", "confidence_score": 0.64, "evidence": [{"clusters": len(payload["relationships"])}]})
        return products[:10]

    async def _ai_enrich(self, database_id: int, payload: dict[str, Any], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            rendered = self.registry.render_prompt("data_product_discovery", {"database_id": database_id, **payload, "data_products": fallback}, category="data_products")
            result = await AIObservabilityService().generate(operation="chat", module="data_products", artifact_type="data_product_discovery", prompt_id=rendered.metadata.id, prompt_version=rendered.metadata.version, model_name=settings.azure_openai_deployment, messages=[{"role": "system", "content": rendered.system_message or "You are a data product discovery engine."}, {"role": "user", "content": rendered.user_prompt}], request_kwargs={"response_format": {"type": "json_object"}}, completeness_score=0.0, coverage_score=0.0, confidence_score=0.0, execution_status="success", fallback_used=False, retry_count=0, extra_metadata={"feature": "data_products"})
            parsed = json.loads(result.content or "{}")
            rows = parsed.get("data_products")
            if isinstance(rows, list) and rows:
                return rows
        except Exception:
            pass
        return fallback

    async def _persist(self, database_id: int, rows: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(DataProduct).where(DataProduct.database_id == database_id))
        for row in rows:
            self.db.add(DataProduct(database_id=database_id, product_name=row["product_name"], product_type=row.get("product_type"), description=row.get("description"), confidence_score=float(row.get("confidence_score", 0.0)), evidence=json.dumps(row.get("evidence", []), default=str), trace_id=row.get("trace_id")))
        await self.db.flush()

    @staticmethod
    def _row(row: DataProduct) -> dict[str, Any]:
        return {"id": row.id, "product_name": row.product_name, "product_type": row.product_type, "description": row.description, "confidence_score": row.confidence_score, "evidence": json.loads(row.evidence or "[]"), "trace_id": row.trace_id, "created_at": row.created_at.isoformat() if row.created_at else None}

    @staticmethod
    def _semantic_row(pkg: SemanticPackage | None) -> dict[str, Any]:
        if not pkg:
            return {}
        return {"business_domain": pkg.business_domain, "business_entities": pkg.business_entities, "business_processes": pkg.business_processes, "confidence_score": pkg.confidence_score}

    @staticmethod
    def _relationship_row(pkg: RelationshipPackage) -> dict[str, Any]:
        return {
            "cluster_id": pkg.cluster_id,
            "domain_name": pkg.domain_name,
            "confidence_score": float(getattr(pkg, "confidence_score", getattr(pkg, "cluster_confidence", 0.0)) or 0.0),
            "cluster_confidence": float(getattr(pkg, "confidence_score", getattr(pkg, "cluster_confidence", 0.0)) or 0.0),
            "entity_graph": pkg.entity_graph,
        }
