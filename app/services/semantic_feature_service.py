"""Feature assembly for semantic intelligence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.metadata import (
    ConnectedDatabase,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
    SemanticPackage,
)


@dataclass
class SemanticFeatureBundle:
    table_id: int
    table_name: str
    schema_name: str
    business_domain_hint: str
    governance_summary: dict[str, Any]
    relationship_context: list[dict[str, Any]]
    statistics: dict[str, Any]
    domain_scores: dict[str, float]
    evidence: list[dict[str, Any]]


class SemanticFeatureService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .options(
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.columns),
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.relationships_from),
            )
            .where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().unique().first()
        if database is None:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def fetch_governance_package(self, database_id: int) -> dict[str, Any]:
        from app.services.column_semantic_service import ColumnSemanticService

        return await ColumnSemanticService(self.db).build_governance_package(database_id)

    async def fetch_semantic_package(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        row = result.scalar_one_or_none()
        if row is None:
            return {
                "database_id": database_id,
                "business_domain": None,
                "semantic_summary": None,
                "business_entities": [],
                "business_processes": [],
                "business_capabilities": [],
                "business_glossary": [],
                "confidence_score": 0.0,
            }
        return {
            "database_id": row.database_id,
            "business_domain": row.business_domain,
            "semantic_summary": row.semantic_summary,
            "business_entities": row.business_entities,
            "business_processes": row.business_processes,
            "business_capabilities": row.business_capabilities,
            "business_glossary": row.business_glossary,
            "confidence_score": row.confidence_score,
            "domain_scores": row.domain_scores,
            "evidence": row.evidence,
        }

    def build_bundle(
        self,
        *,
        database: ConnectedDatabase,
        governance_package: dict[str, Any],
        relationships: list[DatabaseRelationship],
        statistics: dict[str, Any] | None = None,
    ) -> SemanticFeatureBundle:
        table_count = int(governance_package.get("table_count", 0) or 0)
        pii_count = sum(len(pkg.get("pii_columns", [])) for pkg in governance_package.get("packages", []))
        domain_hint = self._derive_domain_hint(governance_package, relationships)
        relationship_context = [
            {
                "source_table": rel.table.name if rel.table else None,
                "target_table": rel.referenced_table_name,
                "source_column": rel.column_name,
                "target_column": rel.referenced_column_name,
            }
            for rel in relationships
        ]
        evidence = [
            {"source": "governance", "table_count": table_count, "pii_count": pii_count},
            {"source": "relationships", "relationship_count": len(relationship_context)},
            {"source": "metadata", "schema_count": len(database.schemas or []), "table_count": sum(len(s.tables or []) for s in (database.schemas or []))},
        ]
        if statistics:
            evidence.append({"source": "statistics", **statistics})
        domain_scores = {
            "governance": min(1.0, pii_count / max(1, table_count * 3)),
            "relationships": min(1.0, len(relationship_context) / max(1, table_count)),
            "metadata": min(1.0, sum(len(schema.tables or []) for schema in (database.schemas or [])) / max(1, table_count)),
        }
        return SemanticFeatureBundle(
            table_id=0,
            table_name="",
            schema_name="",
            business_domain_hint=domain_hint,
            governance_summary=governance_package,
            relationship_context=relationship_context,
            statistics=statistics or {},
            domain_scores=domain_scores,
            evidence=evidence,
        )

    def _derive_domain_hint(self, governance_package: dict[str, Any], relationships: list[DatabaseRelationship]) -> str:
        names = " ".join(
            [governance_package.get("database_id", ""), governance_package.get("business_domain", "") or ""]
        ).lower()
        if any(token in names for token in ["health", "patient", "clinic", "hospital", "diagnosis"]):
            return "Healthcare"
        if any(token in names for token in ["insurance", "policy", "claim"]):
            return "Insurance"
        if any(token in names for token in ["bank", "loan", "payment", "finance", "billing"]):
            return "Financial Services"
        if relationships:
            return "Operational Analytics"
        return "General Business"

