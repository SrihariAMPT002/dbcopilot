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
    GovernancePackage,
    KPIArtifact,
    KPIIntelligence,
    SchemaRelationshipGraph,
    RelationshipPackage,
    SchemaSemantic,
    SemanticPackage,
)
from app.services.ai_observability_service import AIObservabilityService
from app.schema_engine.relationship_graph import RelationshipGraphEngine

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

    MAX_CLUSTER_TABLES = 20
    MAX_CLUSTER_RELATIONSHIPS = 50
    MAX_CLUSTER_ESTIMATED_TOKENS = 4500

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = get_prompt_registry()

    async def generate_for_database(self, database_id: int, job_id: int | None = None) -> dict[str, Any]:
        if not package_is_enabled("kpi"):
            raise ValueError("KPI package is disabled by registry")

        database = await self._fetch_database(database_id)
        governance_packages = await self._fetch_governance_packages(database_id)
        semantic_package = await self._fetch_semantic_package(database_id)
        relationship_packages = await self._fetch_relationship_packages(database_id)
        semantics = await self._fetch_semantics(database_id)
        column_semantics = await self._fetch_column_semantics(database_id)
        clusters = self._relationship_clusters_from_packages(relationship_packages)
        if not clusters:
            graph = await RelationshipGraphEngine(self.db).build_relationship_graph(database_id, persist=False)
            clusters = self._relationship_clusters(graph.edges)
        cluster_results: list[dict[str, Any]] = []
        for cluster_id, table_ids in clusters:
            try:
                cluster_result = await self._discover_for_cluster(
                    database=database,
                    cluster_id=cluster_id,
                    table_ids=table_ids,
                    semantics=semantics,
                    governance_packages=governance_packages,
                    semantic_package=semantic_package,
                    relationship_packages=relationship_packages,
                    column_semantics=column_semantics,
                    job_id=job_id,
                )
            except Exception as exc:
                logger.exception("KPI cluster failed | database_id=%s cluster_id=%s", database_id, cluster_id)
                cluster_result = {
                    "cluster_id": cluster_id,
                    "cluster_name": self._cluster_name(table_ids, semantics),
                    "cluster_size": len(table_ids),
                    "estimated_tokens": 0,
                    "actual_input_tokens": 0,
                    "actual_output_tokens": 0,
                    "execution_status": "failed",
                    "fallback_used": False,
                    "retry_count": 0,
                    "error_message": str(exc),
                    "catalog": [],
                    "definitions": [],
                    "lineage": [],
                    "context": "",
                    "prompt_id": "kpi_discovery",
                    "prompt_version": "clustered",
                    "model_name": settings.azure_openai_deployment,
                    "domain": self._cluster_domain(semantics, table_ids),
                }
            cluster_results.append(cluster_result)

        successful_clusters = [item for item in cluster_results if item.get("execution_status") == "success"]
        failed_clusters = [item for item in cluster_results if item.get("execution_status") != "success"]
        catalog = self._aggregate_catalog([item["catalog"] for item in successful_clusters])
        definitions = self._aggregate_definitions([item["definitions"] for item in successful_clusters])
        lineage = self._aggregate_lineage([item["lineage"] for item in successful_clusters])
        context_md = self._build_context_markdown(database, catalog, definitions, lineage)

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

        confidence_scores = [item.get("confidence", 0.0) for item in catalog if isinstance(item, dict)]

        return {
            "database_id": database_id,
            "database_name": database.display_name or database.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_id": "kpi_discovery",
            "prompt_version": "clustered",
            "model_name": settings.azure_openai_deployment,
            "confidence_score": round(sum(confidence_scores) / max(1, len(confidence_scores)), 3) if confidence_scores else 0.0,
            "kpi_count": len(catalog),
            "coverage": self._coverage(catalog, column_semantics),
            "package_inputs": {
                "governance_packages": len(governance_packages),
                "semantic_package": bool(semantic_package),
                "relationship_packages": len(relationship_packages),
            },
            "successful_clusters": len(successful_clusters),
            "failed_clusters": len(failed_clusters),
            "coverage_percentage": self._cluster_coverage_percentage(successful_clusters, failed_clusters),
            "artifacts": artifacts,
            "catalog": catalog,
            "definitions": definitions,
            "lineage": lineage,
            "context": context_md,
            "cluster_count": len(cluster_results),
            "clusters": [
                {
                    "cluster_id": result["cluster_id"],
                    "cluster_name": result.get("cluster_name"),
                    "domain": result["domain"],
                    "kpi_count": len(result["catalog"]),
                    "execution_status": result.get("execution_status"),
                }
                for result in cluster_results
            ],
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
        *,
        governance_packages: list[GovernancePackage] | None = None,
        semantic_package: SemanticPackage | None = None,
        relationship_packages: list[RelationshipPackage] | None = None,
    ) -> dict[str, Any]:
        db_semantic, table_semantics = semantics
        governance_packages = governance_packages or []
        relationship_packages = relationship_packages or []
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
            "governance_packages": [self._governance_package_to_dict(row) for row in governance_packages],
            "semantic_package": self._semantic_package_to_dict(semantic_package) if semantic_package else {},
            "relationship_packages": [self._relationship_package_to_dict(row) for row in relationship_packages],
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

    @staticmethod
    def _relationship_clusters(edges: list[SchemaRelationshipGraph]) -> list[tuple[str, list[int]]]:
        adjacency: dict[int, set[int]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_table_id, set()).add(edge.target_table_id)
            adjacency.setdefault(edge.target_table_id, set()).add(edge.source_table_id)
        seen: set[int] = set()
        clusters: list[tuple[str, list[int]]] = []
        for start in adjacency:
            if start in seen:
                continue
            stack = [start]
            seen.add(start)
            members: list[int] = []
            while stack:
                node = stack.pop()
                members.append(node)
                for neighbor in adjacency.get(node, set()):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            clusters.append((hashlib.sha256(json.dumps(sorted(members)).encode("utf-8")).hexdigest()[:16], sorted(members)))
        return clusters

    def _cluster_domain(
        self,
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        table_ids: list[int],
    ) -> str:
        db_semantic, table_semantics = semantics
        table_lookup = {table.id: semantic for semantic, table in table_semantics}
        domain_votes = [table_lookup[table_id].semantic_summary for table_id in table_ids if table_id in table_lookup]
        if db_semantic and db_semantic.business_domain:
            return db_semantic.business_domain
        for vote in domain_votes:
            if vote:
                return str(vote)[:128]
        return "general"

    def _cluster_name(
        self,
        table_ids: list[int],
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
    ) -> str:
        _, table_semantics = semantics
        lookup = {table.id: table for _, table in table_semantics}
        names = [f"{lookup[table_id].schema.name}.{lookup[table_id].name}" for table_id in table_ids if table_id in lookup]
        if not names:
            return "empty-cluster"
        return names[0] if len(names) == 1 else f"{names[0]} +{len(names) - 1}"

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        return max(1, len(text or "") // 4)

    def _estimate_prompt_tokens(self, payload: dict[str, Any]) -> int:
        return self._estimate_text_tokens(json.dumps(payload, default=str, sort_keys=True))

    def _apply_cluster_budget(
        self,
        prompt_context: dict[str, Any],
        cluster_relationships: list[SchemaRelationshipGraph],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        budgeted = dict(prompt_context)
        budgeted["cluster_tables"] = (prompt_context.get("cluster_tables") or [])[: self.MAX_CLUSTER_TABLES]
        budgeted["cluster_relationships"] = (prompt_context.get("cluster_relationships") or [])[: self.MAX_CLUSTER_RELATIONSHIPS]
        budgeted["governance_intelligence"] = (prompt_context.get("governance_intelligence") or [])[: self.MAX_CLUSTER_TABLES]
        estimated_tokens = self._estimate_prompt_tokens(budgeted)
        prompt_truncated = len(prompt_context.get("cluster_tables") or []) > self.MAX_CLUSTER_TABLES or len(cluster_relationships) > self.MAX_CLUSTER_RELATIONSHIPS
        if estimated_tokens > self.MAX_CLUSTER_ESTIMATED_TOKENS:
            prompt_truncated = True
            budgeted["cluster_tables"] = budgeted["cluster_tables"][: max(1, self.MAX_CLUSTER_TABLES // 2)]
            budgeted["cluster_relationships"] = budgeted["cluster_relationships"][: max(1, self.MAX_CLUSTER_RELATIONSHIPS // 2)]
            budgeted["governance_intelligence"] = budgeted["governance_intelligence"][: max(1, self.MAX_CLUSTER_TABLES // 2)]
            estimated_tokens = self._estimate_prompt_tokens(budgeted)
        return budgeted, {
            "cluster_size": len(prompt_context.get("cluster_tables") or []),
            "estimated_tokens": estimated_tokens,
            "prompt_truncated": prompt_truncated,
        }

    @staticmethod
    def _parse_required_json(response_text: str) -> dict[str, Any]:
        text = (response_text or "").strip()
        if not text:
            raise ValueError("empty_ai_response")
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise ValueError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_json")
        required = ["kpi_catalog", "kpi_definitions", "kpi_lineage", "kpi_context"]
        missing = [field for field in required if field not in payload or payload[field] in (None, "", [], {})]
        if missing:
            raise ValueError(f"missing_required_sections:{','.join(missing)}")
        return payload

    def _cluster_prompt_context(
        self,
        database: ConnectedDatabase,
        cluster_id: str,
        table_ids: list[int],
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        relationships: list[SchemaRelationshipGraph],
        column_semantics: list[ColumnSemantic],
        *,
        governance_packages: list[GovernancePackage] | None = None,
        semantic_package: SemanticPackage | None = None,
        relationship_packages: list[RelationshipPackage] | None = None,
    ) -> dict[str, Any]:
        db_semantic, table_semantics = semantics
        table_lookup = {table.id: (semantic, table) for semantic, table in table_semantics}
        cluster_tables = [table_lookup[table_id][1] for table_id in table_ids if table_id in table_lookup]
        if relationship_packages:
            cluster_relationships = [
                rel for rel in relationship_packages if any(str(table_id) in (rel.cluster_id or "") for table_id in table_ids)
            ]
        else:
            cluster_relationships = [
                rel for rel in relationships if rel.source_table_id in table_ids or rel.target_table_id in table_ids
            ]
        cluster_columns = [sem for sem in column_semantics if sem.database_id == database.id]
        domain = self._cluster_domain(semantics, table_ids)
        return {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "semantic_domain": domain,
            "cluster_id": cluster_id,
            "cluster_name": self._cluster_name(table_ids, semantics),
            "cluster_table_count": len(cluster_tables),
            "cluster_tables": [
                {
                    "schema": table.schema.name,
                    "table": table.name,
                    "description": table.description,
                    "semantic_summary": table_lookup[table.id][0].semantic_summary if table.id in table_lookup else None,
                }
                for table in cluster_tables
            ],
            "cluster_relationships": [
                {
                    "source_schema": rel.source_schema_name,
                    "source_table": rel.source_table_name,
                    "target_schema": rel.target_schema_name,
                    "target_table": rel.target_table_name,
                    "ai_summary": rel.ai_summary,
                    "cluster_id": rel.cluster_id,
                }
                for rel in cluster_relationships
            ],
            "database_semantics": {
                "business_domain": db_semantic.business_domain if db_semantic else None,
                "business_summary": db_semantic.business_summary if db_semantic else None,
            },
            "semantic_package": self._semantic_package_to_dict(semantic_package) if semantic_package else {},
            "governance_packages": [self._governance_package_to_dict(row) for row in (governance_packages or [])],
            "governance_intelligence": [
                {
                    "column": sem.column_name,
                    "is_pii": sem.is_pii,
                    "risk_level": sem.risk_level,
                    "confidence": sem.confidence_score,
                }
                for sem in cluster_columns
            ],
        }

    async def _discover_for_cluster(
        self,
        *,
        database: ConnectedDatabase,
        cluster_id: str,
        table_ids: list[int],
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        graph: Any,
        column_semantics: list[ColumnSemantic],
        job_id: int | None,
    ) -> dict[str, Any]:
        cluster_relationships = [edge for edge in graph.edges if edge.source_table_id in table_ids or edge.target_table_id in table_ids]
        governance_packages = await self._fetch_governance_packages(database.id)
        semantic_package = await self._fetch_semantic_package(database.id)
        relationship_packages = await self._fetch_relationship_packages(database.id)
        prompt_context = self._cluster_prompt_context(
            database,
            cluster_id,
            table_ids,
            semantics,
            cluster_relationships,
            column_semantics,
            governance_packages=governance_packages,
            semantic_package=semantic_package,
            relationship_packages=relationship_packages,
        )
        prompt_context, telemetry = self._apply_cluster_budget(prompt_context, cluster_relationships)
        rendered = self.registry.render_prompt("kpi_discovery", prompt_context, category="kpi")
        ai_result = await self._call_azure_openai(database, rendered, job_id=job_id, cluster_id=cluster_id, cluster_size=telemetry["cluster_size"], domain=prompt_context["semantic_domain"])
        parsed_payload = self._parse_required_json(ai_result.content or "")
        return {
            "cluster_id": cluster_id,
            "cluster_name": prompt_context["cluster_name"],
            "cluster_size": telemetry["cluster_size"],
            "estimated_tokens": telemetry["estimated_tokens"],
            "actual_input_tokens": int(ai_result.token_usage.get("prompt_tokens", 0) or 0),
            "actual_output_tokens": int(ai_result.token_usage.get("completion_tokens", 0) or 0),
            "execution_status": "success",
            "fallback_used": False,
            "retry_count": 0,
            "trace_id": getattr(ai_result, "trace_id", None),
            "domain": prompt_context["semantic_domain"],
            "catalog": parsed_payload["kpi_catalog"],
            "definitions": parsed_payload["kpi_definitions"],
            "lineage": parsed_payload["kpi_lineage"],
            "context": parsed_payload["kpi_context"],
            "prompt_id": rendered.metadata.id,
            "prompt_version": rendered.metadata.version,
            "model_name": ai_result.model_name,
        }

    @staticmethod
    def _aggregate_catalog(collections: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for catalog in collections:
            for item in catalog:
                key = item.get("name")
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        return merged

    def _aggregate_definitions(self, collections: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        catalog = self._aggregate_catalog(collections)
        return self._build_definitions(catalog)

    def _aggregate_lineage(self, collections: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for lineage in collections:
            merged.extend(lineage)
        return merged

    @staticmethod
    def _stage_metadata_fingerprint(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, default=str, sort_keys=True).encode("utf-8")).hexdigest()[:32]

    async def _call_azure_openai(self, database: ConnectedDatabase, rendered_prompt: Any, *, job_id: int | None = None, cluster_id: str | None = None, cluster_size: int | None = None, domain: str | None = None):
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
            execution_status="success",
            fallback_used=False,
            retry_count=0,
            extra_metadata={
                "database_id": database.id,
                "job_id": job_id,
                "stage": "kpi",
                "cluster_id": cluster_id,
                "cluster_size": cluster_size,
                "semantic_domain": domain,
                "module": "kpi_intelligence",
                "prompt_id": rendered_prompt.metadata.id,
                "prompt_version": rendered_prompt.metadata.version,
                "execution_status": "success",
                "fallback_used": False,
                "metadata_fingerprint": self._stage_metadata_fingerprint(database.id, job_id, rendered_prompt.metadata.id, rendered_prompt.metadata.version),
            },
        )
        return ai_result

    def _discover_kpis(
        self,
        database: ConnectedDatabase,
        semantics: tuple[DatabaseSemantic | None, list[tuple[SchemaSemantic, DatabaseTable]]],
        relationships: list[Any],
        column_semantics: list[ColumnSemantic],
    ) -> list[dict[str, Any]]:
        db_semantic, table_semantics = semantics
        kpis: list[dict[str, Any]] = []
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

    @staticmethod
    def _relationship_clusters_from_packages(packages: list[RelationshipPackage]) -> list[tuple[str, list[int]]]:
        clusters: dict[str, list[int]] = {}
        for package in packages:
            cluster_key = package.cluster_id or "database"
            members = clusters.setdefault(cluster_key, [])
            for entry in package.entity_graph:
                for table_id_key in ("source_table_id", "target_table_id"):
                    table_id = entry.get(table_id_key)
                    if isinstance(table_id, int) and table_id not in members:
                        members.append(table_id)
        return [(cluster_id, sorted(table_ids)) for cluster_id, table_ids in clusters.items() if table_ids]

    def _build_lineage(self, catalog: list[dict[str, Any]], relationships: list[Any]) -> list[dict[str, Any]]:
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

    @staticmethod
    def _cluster_coverage_percentage(successful_clusters: list[dict[str, Any]], failed_clusters: list[dict[str, Any]]) -> float:
        total = len(successful_clusters) + len(failed_clusters)
        if total <= 0:
            return 0.0
        return round((len(successful_clusters) / total) * 100.0, 2)

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
                    cluster_id=item.get("cluster_id"),
                    cluster_name=item.get("cluster_name"),
                    cluster_size=int(item.get("cluster_size", 0) or 0) if item.get("cluster_size") is not None else None,
                    estimated_tokens=int(item.get("estimated_tokens", 0) or 0) if item.get("estimated_tokens") is not None else None,
                    actual_input_tokens=int(item.get("actual_input_tokens", 0) or 0) if item.get("actual_input_tokens") is not None else None,
                    actual_output_tokens=int(item.get("actual_output_tokens", 0) or 0) if item.get("actual_output_tokens") is not None else None,
                    prompt_id=item.get("prompt_id", "kpi_discovery"),
                    prompt_version=item.get("prompt_version", "clustered"),
                    model_name=item.get("model_name", settings.azure_openai_deployment),
                    execution_status=item.get("execution_status"),
                    used_fallback=bool(item.get("used_fallback", False)),
                    retry_count=int(item.get("retry_count", 0) or 0),
                    trace_id=item.get("trace_id"),
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
            "cluster_id": row.cluster_id,
            "cluster_name": row.cluster_name,
            "cluster_size": row.cluster_size,
            "estimated_tokens": row.estimated_tokens,
            "actual_input_tokens": row.actual_input_tokens,
            "actual_output_tokens": row.actual_output_tokens,
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

    @staticmethod
    def _governance_package_to_dict(row: GovernancePackage) -> dict[str, Any]:
        return {
            "id": row.id,
            "database_id": row.database_id,
            "table_id": row.table_id,
            "table_name": row.table_name,
            "schema_name": row.schema_name,
            "table_summary": row.table_summary,
            "business_purpose": row.business_purpose,
            "pii_columns": row.pii_columns,
            "risk_columns": row.risk_columns,
            "sensitive_columns": row.sensitive_columns,
            "overall_risk": row.overall_risk,
            "confidence_score": row.confidence_score,
        }

    @staticmethod
    def _semantic_package_to_dict(row: SemanticPackage) -> dict[str, Any]:
        return {
            "id": row.id,
            "database_id": row.database_id,
            "business_domain": row.business_domain,
            "semantic_summary": row.semantic_summary,
            "business_entities": row.business_entities,
            "business_processes": row.business_processes,
            "business_capabilities": row.business_capabilities,
            "business_glossary": row.business_glossary,
            "confidence_score": row.confidence_score,
        }

    @staticmethod
    def _relationship_package_to_dict(row: RelationshipPackage) -> dict[str, Any]:
        return {
            "id": row.id,
            "database_id": row.database_id,
            "cluster_id": row.cluster_id,
            "domain_name": row.domain_name,
            "cluster_summary": row.cluster_summary,
            "entity_graph": row.entity_graph,
            "business_process_flows": row.business_process_flows,
            "hidden_relationships": row.hidden_relationships,
            "upstream_dependencies": row.upstream_dependencies,
            "downstream_dependencies": row.downstream_dependencies,
            "lifecycle_flows": row.lifecycle_flows,
            "confidence_score": row.confidence_score,
        }
