"""KPI intelligence discovery and artifact generation."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.prompts import get_prompt_registry
from app.config.package_registry import package_is_enabled
from app.core.config import settings
from app.models.artifact_manifest import ArtifactType
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    KPIArtifact,
    KPIIntelligence,
    SchemaRelationshipGraph,
    SchemaSemantic,
)
from app.services.ai_observability_service import AIObservabilityService

logger = logging.getLogger(__name__)


@dataclass
class KPIArtifactBundle:
    artifact_type: ArtifactType
    filename: str
    mime: str
    content: str
    generated_at: datetime
    version: int


class KPIIntelligenceService:
    """Deterministic KPI discovery using semantic and relationship metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int, job_id: int | None = None) -> dict[str, Any]:
        if not package_is_enabled("kpi"):
            raise ValueError("KPI package is disabled by registry")

        database = await self._fetch_database(database_id)
        semantics = await self._fetch_semantics(database_id)
        relationships = await self._fetch_relationships(database_id)
        column_semantics = await self._fetch_column_semantics(database_id)

        prompt_context = self._build_prompt_context(database, semantics, relationships, column_semantics)
        rendered = self.registry.render_prompt("kpi_discovery", prompt_context, category="kpi")
        ai_result = await self._call_azure_openai(database, rendered, job_id=job_id)
        parsed = self._parse_response(ai_result.content or "", database, semantics, relationships, column_semantics)
        catalog = parsed["catalog"]
        definitions = parsed["definitions"]
        lineage = parsed["lineage"]
        context_md = parsed["context"]

        await self._persist_kpis(database_id, catalog)

        bundles = [
            (ArtifactType.kpi_catalog, json.dumps(catalog, indent=2, default=str), "application/json"),
            (ArtifactType.kpi_definitions, json.dumps(definitions, indent=2, default=str), "application/json"),
            (ArtifactType.kpi_lineage, json.dumps(lineage, indent=2, default=str), "application/json"),
            (ArtifactType.kpi_context, context_md, "text/markdown"),
        ]

        artifacts = []
        for artifact_type, content, mime in bundles:
            artifacts.append(await self._store_artifact(database_id, artifact_type, content, mime=mime))

        return {
            "database_id": database_id,
            "database_name": database.display_name or database.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_id": rendered.metadata.id,
            "prompt_version": rendered.metadata.version,
            "model_name": ai_result.model_name,
            "confidence_score": ai_result.metadata.get("confidence_score", 0.0) if ai_result.metadata else 0.0,
            "kpi_count": len(catalog),
            "coverage": self._coverage(catalog, column_semantics),
            "artifacts": artifacts,
            "catalog": catalog,
            "definitions": definitions,
            "lineage": lineage,
            "context": context_md,
        }

    async def get_latest_package(self, database_id: int) -> dict[str, Any]:
        records = await self._fetch_artifacts(database_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped.setdefault(record.artifact_type, []).append(self._artifact_row(record))
        latest = {k: v[0] for k, v in grouped.items() if v}
        return {"latest": latest, "history": grouped, "artifact_count": len(records)}

    async def get_current_catalog(self, database_id: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(KPIIntelligence).where(KPIIntelligence.database_id == database_id).order_by(KPIIntelligence.name)
        )
        return [self._kpi_row(row) for row in result.scalars().all()]

    def _build_prompt_context(
        self,
        database: ConnectedDatabase,
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        relationships: list[SchemaRelationshipGraph],
        column_semantics: list[ColumnSemantic],
    ) -> dict[str, Any]:
        db_semantic, table_semantics = semantics
        return {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "database_semantics": {
                "business_domain": db_semantic.business_domain if db_semantic else None,
                "business_summary": db_semantic.business_summary if db_semantic else None,
                "analysis_notes": db_semantic.analysis_notes if db_semantic else None,
                "key_entities": db_semantic.key_entities if db_semantic else [],
                "business_glossary": db_semantic.business_glossary if db_semantic else [],
                "suggested_use_cases": db_semantic.suggested_use_cases if db_semantic else [],
            },
            "schema_semantics": [
                {
                    "schema": table.schema.name,
                    "table": table.name,
                    "semantic_summary": semantic.semantic_summary,
                    "business_entity": semantic.business_entity,
                    "business_process": semantic.business_process,
                }
                for semantic, table in table_semantics
            ],
            "relationship_intelligence": [
                {
                    "source_schema": rel.source_schema_name,
                    "source_table": rel.source_table_name,
                    "target_schema": rel.target_schema_name,
                    "target_table": rel.target_table_name,
                    "join_type": rel.join_type,
                    "ai_summary": rel.ai_summary,
                }
                for rel in relationships
            ],
            "governance_intelligence": [
                {
                    "column": sem.column_name,
                    "is_pii": sem.is_pii,
                    "pii_type": sem.pii_type,
                    "risk_level": sem.risk_level,
                    "confidence": sem.confidence_score,
                }
                for sem in column_semantics
            ],
            "database_context": {
                "table_count": len(table_semantics),
                "relationship_count": len(relationships),
                "column_count": len(column_semantics),
            },
        }

    async def _call_azure_openai(self, database: ConnectedDatabase, rendered_prompt: Any, *, job_id: int | None = None):
        observability = AIObservabilityService()
        ai_result = await observability.generate(
            operation="chat",
            module="kpi_intelligence",
            artifact_type="kpi_discovery",
            database_id=database.id,
            database_name=database.display_name or database.name,
            prompt_id=rendered_prompt.metadata.id,
            prompt_version=rendered_prompt.metadata.version,
            model_name=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": rendered_prompt.system_message or "You are a KPI discovery assistant.",
                },
                {"role": "user", "content": rendered_prompt.user_prompt},
            ],
            request_kwargs={
                "max_completion_tokens": 4000,
                "response_format": {"type": "json_object"},
            },
            completeness_score=0.0,
            coverage_score=0.0,
            confidence_score=0.0,
            extra_metadata={
                "database_id": database.id,
                "job_id": None,
                "module": "kpi_intelligence",
                "prompt_id": rendered_prompt.metadata.id,
                "prompt_version": rendered_prompt.metadata.version,
                "job_id": job_id,
            },
        )
        return ai_result

    def _parse_response(
        self,
        response_text: str,
        database: ConnectedDatabase,
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        relationships: list[SchemaRelationshipGraph],
        column_semantics: list[ColumnSemantic],
    ) -> dict[str, Any]:
        try:
            payload = json.loads(self._extract_json_payload(response_text))
        except Exception:
            payload = {}
        catalog = payload.get("catalog") or self._discover_kpis(database, semantics, relationships, column_semantics)
        definitions = payload.get("definitions") or self._build_definitions(catalog)
        lineage = payload.get("lineage") or self._build_lineage(catalog, relationships)
        context = payload.get("context") or self._build_context_markdown(database, catalog, definitions, lineage)
        return {
            "catalog": catalog,
            "definitions": definitions,
            "lineage": lineage,
            "context": context,
        }

    @staticmethod
    def _extract_json_payload(response_text: str) -> str:
        text = (response_text or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def _discover_kpis(
        self,
        database: ConnectedDatabase,
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        relationships: list[SchemaRelationshipGraph],
        column_semantics: list[ColumnSemantic],
    ) -> list[dict[str, Any]]:
        db_semantic, table_semantics = semantics
        kpis: list[dict[str, Any]] = []
        table_lookup = {table.id: table for _, table in table_semantics}
        for semantic, table in table_semantics:
            measurable_cols = [c for c in table.columns if any(token in c.name.lower() for token in ["count", "amount", "total", "revenue", "price", "qty", "quantity", "balance", "score"])]
            if not measurable_cols:
                continue
            base_name = f"{table.name} performance"
            confidence = 0.55
            if db_semantic and db_semantic.business_domain:
                confidence += 0.1
            if relationships:
                confidence += 0.1
            if semantic and semantic.semantic_summary:
                confidence += 0.1
            kpis.append(
                {
                    "name": base_name,
                    "description": f"Core KPI family inferred from {table.schema.name}.{table.name}.",
                    "business_meaning": semantic.semantic_summary if semantic else "",
                    "formula": f"SUM({measurable_cols[0].name})",
                    "source_tables": [f"{table.schema.name}.{table.name}"],
                    "source_columns": [col.name for col in measurable_cols[:5]],
                    "dimensions": [c.name for c in table.columns[:5] if c.name not in {col.name for col in measurable_cols}],
                    "filters": [],
                    "confidence": round(min(0.95, confidence), 2),
                    "owner": db_semantic.business_domain if db_semantic and db_semantic.business_domain else None,
                    "lineage_summary": f"Derived from {table.schema.name}.{table.name} with related semantic summary.",
                    "discovery_source": "deterministic_batch",
                    "package_version": "1.0",
                    "status": "discovered",
                }
            )

        if not kpis and table_semantics:
            _, table = table_semantics[0]
            kpis.append(
                {
                    "name": f"{table.name} activity",
                    "description": f"Fallback KPI inferred from {table.schema.name}.{table.name}.",
                    "business_meaning": table.description or "",
                    "formula": "COUNT(*)",
                    "source_tables": [f"{table.schema.name}.{table.name}"],
                    "source_columns": ["*"],
                    "dimensions": [table.schema.name],
                    "filters": [],
                    "confidence": 0.35,
                    "owner": db_semantic.business_domain if db_semantic and db_semantic.business_domain else None,
                    "lineage_summary": "Fallback discovery path.",
                    "discovery_source": "fallback",
                    "package_version": "1.0",
                    "status": "discovered",
                }
            )
        return kpis

    def _build_definitions(self, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": item["name"],
                "description": item["description"],
                "formula": item["formula"],
                "dimensions": item["dimensions"],
                "filters": item["filters"],
                "source_tables": item["source_tables"],
                "source_columns": item["source_columns"],
                "grain": "table-level",
                "aggregation_logic": "heuristic",
                "caveats": ["Deterministic first-pass KPI discovery; validate before production use."],
            }
            for item in catalog
        ]

    def _build_lineage(self, catalog: list[dict[str, Any]], relationships: list[SchemaRelationshipGraph]) -> list[dict[str, Any]]:
        return [
            {
                "name": item["name"],
                "lineage_summary": item["lineage_summary"],
                "source_tables": item["source_tables"],
                "source_columns": item["source_columns"],
                "join_path": [
                    f"{rel.source_schema_name}.{rel.source_table_name}->{rel.target_schema_name}.{rel.target_table_name}"
                    for rel in relationships[:5]
                ],
                "transformations": [],
                "dependency_chain": item["source_tables"],
            }
            for item in catalog
        ]

    def _build_context_markdown(
        self,
        database: ConnectedDatabase,
        catalog: list[dict[str, Any]],
        definitions: list[dict[str, Any]],
        lineage: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"# KPI Context for {database.display_name or database.name}",
            "",
            f"Discovered KPIs: {len(catalog)}",
            "",
            "## KPI Catalog",
        ]
        for item in catalog:
            lines.append(f"- {item['name']}: {item['business_meaning'] or item['description']}")
        lines.append("")
        lines.append("## KPI Definitions")
        for item in definitions:
            lines.append(f"- {item['name']}: {item['formula']}")
        lines.append("")
        lines.append("## KPI Lineage")
        for item in lineage:
            lines.append(f"- {item['name']}: {item['lineage_summary']}")
        return "\n".join(lines)

    def _coverage(self, catalog: list[dict[str, Any]], column_semantics: list[ColumnSemantic]) -> dict[str, Any]:
        total_columns = max(1, len(column_semantics))
        return {
            "kpi_count": len(catalog),
            "coverage_score": round(min(1.0, len(catalog) / total_columns), 3),
            "confidence_score": round(sum(item["confidence"] for item in catalog) / max(1, len(catalog)), 3) if catalog else 0.0,
        }

    async def _store_artifact(self, database_id: int, artifact_type: ArtifactType, content: str, *, mime: str) -> dict[str, Any]:
        path = Path("/tmp/artifacts_registry")
        path.mkdir(parents=True, exist_ok=True)
        version = await self._next_version(database_id, artifact_type.value)
        filename = f"db_{database_id}_{artifact_type.value}_v{version}"
        if artifact_type == ArtifactType.kpi_context:
            filename += ".md"
        else:
            filename += ".json"
        full_path = path / filename
        full_path.write_text(content, encoding="utf-8")

        record = KPIArtifact(
            database_id=database_id,
            prompt_id="kpi_discovery",
            prompt_version="1.0",
            model_name=settings.azure_openai_deployment,
            artifact_type=artifact_type.value,
            version=version,
            schema_hash=self._schema_hash(content),
            confidence_score=0.0,
            metadata_fingerprint=self._schema_hash({"artifact_type": artifact_type.value, "content": content}),
            artifact_path=str(full_path),
            mime=mime,
        )
        self.db.add(record)
        await self.db.flush()
        return self._artifact_row(record)

    async def _persist_kpis(self, database_id: int, catalog: list[dict[str, Any]]) -> None:
        await self.db.execute(delete(KPIIntelligence).where(KPIIntelligence.database_id == database_id))
        for item in catalog:
            fingerprint = self._schema_hash(item)
            self.db.add(
                KPIIntelligence(
                    database_id=database_id,
                    prompt_id=item.get("prompt_id", "kpi_discovery"),
                    prompt_version=item.get("prompt_version", "1.0"),
                    model_name=item.get("model_name", settings.azure_openai_deployment),
                    name=item["name"],
                    description=item.get("description"),
                    business_meaning=item.get("business_meaning"),
                    formula=item.get("formula"),
                    source_tables=json.dumps(item.get("source_tables", []), default=str),
                    source_columns=json.dumps(item.get("source_columns", []), default=str),
                    dimensions=json.dumps(item.get("dimensions", []), default=str),
                    filters=json.dumps(item.get("filters", []), default=str),
                    confidence=float(item.get("confidence", 0.0)),
                    owner=item.get("owner"),
                    lineage_summary=item.get("lineage_summary"),
                    discovery_source=item.get("discovery_source"),
                    package_version=item.get("package_version"),
                    confidence_score=float(item.get("confidence", 0.0)),
                    metadata_fingerprint=fingerprint,
                    status=item.get("status", "discovered"),
                )
            )
        await self.db.flush()

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(select(ConnectedDatabase).where(ConnectedDatabase.id == database_id))
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _fetch_semantics(self, database_id: int) -> tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]]:
        db_semantic = await self.db.scalar(select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id))
        result = await self.db.execute(
            select(SchemaSemantic, DatabaseTable)
            .join(DatabaseTable, SchemaSemantic.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .options(
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.schema),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return db_semantic, [(semantic, table) for semantic, table in result.all()]

    async def _fetch_relationships(self, database_id: int) -> list[SchemaRelationshipGraph]:
        result = await self.db.execute(
            select(SchemaRelationshipGraph)
            .where(SchemaRelationshipGraph.database_id == database_id)
            .order_by(SchemaRelationshipGraph.source_schema_name, SchemaRelationshipGraph.source_table_name)
        )
        return list(result.scalars().all())

    async def _fetch_column_semantics(self, database_id: int) -> list[ColumnSemantic]:
        result = await self.db.execute(select(ColumnSemantic).where(ColumnSemantic.database_id == database_id))
        return list(result.scalars().all())

    async def _fetch_artifacts(self, database_id: int) -> list[KPIArtifact]:
        result = await self.db.execute(
            select(KPIArtifact).where(KPIArtifact.database_id == database_id).order_by(KPIArtifact.generated_at.desc())
        )
        return list(result.scalars().all())

    async def _next_version(self, database_id: int, artifact_type: str) -> int:
        result = await self.db.execute(
            select(KPIArtifact)
            .where(KPIArtifact.database_id == database_id, KPIArtifact.artifact_type == artifact_type)
            .order_by(KPIArtifact.version.desc())
            .limit(1)
        )
        latest = result.scalars().first()
        return (latest.version + 1) if latest else 1

    @staticmethod
    def _schema_hash(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _artifact_row(record: KPIArtifact) -> dict[str, Any]:
        return {
            "id": record.id,
            "prompt_id": record.prompt_id,
            "prompt_version": record.prompt_version,
            "model_name": record.model_name,
            "artifact_type": record.artifact_type,
            "version": record.version,
            "schema_hash": record.schema_hash,
            "confidence_score": record.confidence_score,
            "metadata_fingerprint": record.metadata_fingerprint,
            "artifact_path": record.artifact_path,
            "mime": record.mime,
            "generated_at": record.generated_at.isoformat() if record.generated_at else None,
        }

    @staticmethod
    def _kpi_row(row: KPIIntelligence) -> dict[str, Any]:
        return {
            "id": row.id,
            "database_id": row.database_id,
            "name": row.name,
            "prompt_id": row.prompt_id,
            "prompt_version": row.prompt_version,
            "model_name": row.model_name,
            "description": row.description,
            "business_meaning": row.business_meaning,
            "formula": row.formula,
            "source_tables": json.loads(row.source_tables or "[]"),
            "source_columns": json.loads(row.source_columns or "[]"),
            "dimensions": json.loads(row.dimensions or "[]"),
            "filters": json.loads(row.filters or "[]"),
            "confidence": row.confidence,
            "owner": row.owner,
            "lineage_summary": row.lineage_summary,
            "discovery_source": row.discovery_source,
            "package_version": row.package_version,
            "confidence_score": row.confidence_score,
            "metadata_fingerprint": row.metadata_fingerprint,
            "status": row.status,
        }
