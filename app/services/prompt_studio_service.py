"""
Prompt Studio artifact generation service.

Builds database-context artifacts from semantic intelligence, relationship
graph, metadata, and embedding metadata using YAML templates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.prompts import PromptRegistry, get_prompt_registry
from app.config.package_registry import package_artifacts, package_is_enabled
from app.core.config import settings
from app.models.artifact_manifest import ArtifactType
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseSemantic, DatabaseTable
from app.models.metadata import KPIIntelligence, GovernancePackage, RelationshipPackage, SchemaRelationshipGraph, SemanticPackage
from app.services.ai_observability_service import AIObservabilityService
from app.schema_engine.embeddings import EmbeddingEngine
from app.services.artifact_service import ArtifactService
from app.services.column_semantic_service import ColumnSemanticService
from app.utils import now_utc

logger = logging.getLogger(__name__)


@dataclass
class PromptStudioArtifact:
    artifact_type: ArtifactType
    template_id: str
    prompt_version: str
    model_name: str
    filename: str
    mime: str
    content: str
    generated_at: datetime
    manifest: Optional[dict[str, Any]] = None


@dataclass
class ContextPackageResult:
    artifact_type: ArtifactType
    prompt_id: str
    prompt_version: str
    model_name: str
    content: str
    mime: str
    filename: str
    context_quality_score: float
    governance_coverage: float
    pii_coverage: float
    generated_at: datetime
    manifest: Optional[dict[str, Any]] = None


@dataclass
class GeneratedPromptResult:
    artifact_type: ArtifactType
    prompt_id: str
    prompt_version: str
    model_name: str
    content: str
    filename: str
    generated_at: datetime
    trace_id: str | None
    confidence_score: float
    manifest: Optional[dict[str, Any]] = None


class PromptStudioService:
    """Generate versioned Prompt Studio artifacts from shared metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry: PromptRegistry = get_prompt_registry()
        self.artifact_service = ArtifactService(db)

    @staticmethod
    def _is_sensitive_field(
        is_pii: bool = False,
        risk_level: str | None = None,
    ) -> bool:
        if not settings.pii_prompt_protection_enabled:
            return False
        if is_pii:
            return True
        return bool(risk_level and risk_level.lower() in {"high", "critical"})

    @staticmethod
    def _redact_text(text: str) -> str:
        if not settings.pii_prompt_protection_enabled or not text.strip():
            return text
        return "[REDACTED]"

    @classmethod
    def _redact_context(cls, context: dict[str, Any]) -> dict[str, Any]:
        redacted = json.loads(json.dumps(context, default=str))
        semantic = redacted.get("semantic") or {}
        columns = redacted.get("columns") or []
        for column in columns:
            if cls._is_sensitive_field(
                is_pii=bool(column.get("is_pii")),
                risk_level=column.get("risk_level"),
            ):
                column["name"] = "[PII REDACTED]"
                if column.get("description"):
                    column["description"] = "[PII REDACTED]"
                if column.get("pii_type"):
                    column["pii_type"] = "[REDACTED]"
        for table in columns:
            if isinstance(table, dict):
                for field in ("business_description", "analysis_notes"):
                    if field in table and table.get(field):
                        table[field] = cls._redact_text(str(table[field]))
        if semantic.get("business_summary"):
            semantic["business_summary"] = cls._redact_text(str(semantic["business_summary"]))
        redacted["semantic"] = semantic
        return redacted

    def _prompt_context_for_artifact(self, artifact_type: str, context: dict[str, Any]) -> dict[str, Any]:
        redacted_types = {
            ArtifactType.database_context.value,
            ArtifactType.system_prompt.value,
            ArtifactType.rag_context.value,
            ArtifactType.agent_context.value,
            ArtifactType.text_to_sql_context.value,
        }
        if artifact_type in redacted_types:
            return self._redact_context(context)
        return context

    @staticmethod
    def _safe_json(value: Any) -> str:
        return json.dumps(value, indent=2, default=str, ensure_ascii=False)

    @staticmethod
    def _compute_quality(context: dict[str, Any]) -> dict[str, float]:
        semantic = context.get("semantic") or {}
        governance = context.get("governance") or {}
        relationship_intel = context.get("relationship_intelligence") or {}
        embeddings = context.get("embeddings") or {}
        columns = context.get("columns") or []
        column_count = max(1, len(columns))
        pii_count = sum(1 for col in columns if col.get("is_pii"))
        quality = min(
            1.0,
            0.20 * bool(semantic.get("business_summary"))
            + 0.20 * bool(relationship_intel.get("ai_summary"))
            + 0.20 * min(1.0, len(semantic.get("key_entities", [])) / 5.0)
            + 0.20 * min(1.0, pii_count / column_count)
            + 0.20 * min(1.0, float(embeddings.get("indexed_tables", 0)) / max(1, float(context.get("table_count", 1))))
        )
        return {
            "context_quality_score": round(quality, 3),
            "governance_coverage": round(
                min(1.0, 0.5 * float(governance.get("prompt_protection_enabled", False)) + 0.5 * float(governance.get("embedding_protection_enabled", False))),
                3,
            ),
            "pii_coverage": round(min(1.0, pii_count / column_count), 3),
        }

    def _assemble_context_payload(self, artifact_type: ArtifactType, context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "database_id": context["database_id"],
            "database_name": context["database_name"],
            "database_type": context["database_type"],
            "generated_at": context["generated_at"],
            "artifact_type": artifact_type.value,
            "semantic": context.get("semantic", {}),
            "relationship_intelligence": context.get("relationship_intelligence", {}),
            "embeddings": context.get("embeddings", {}),
            "governance": context.get("governance", {}),
            "readiness": context.get("readiness", {}),
            "business_glossary": (context.get("semantic") or {}).get("business_glossary", []),
            "tables": context.get("tables", []),
            "columns": context.get("columns", []),
            "schema_count": context.get("schema_count", 0),
            "table_count": context.get("table_count", 0),
            "column_count": context.get("column_count", 0),
            "relationship_count": context.get("relationship_count", 0),
            "relationships": (context.get("relationship_graph") or {}).edges if getattr(context.get("relationship_graph"), "edges", None) else [],
        }
        return self._prompt_context_for_artifact(artifact_type.value, payload)

    def _assemble_generation_context(self, context: dict[str, Any], template_id: str) -> dict[str, Any]:
        payload = self._assemble_context_payload(ArtifactType.system_prompt, context)
        payload.update(
            {
                "template_id": template_id,
                "governance_packages": context.get("governance_packages", []),
                "semantic_package": context.get("semantic", {}).get("semantic_package", {}),
                "relationship_packages": context.get("relationship_packages", []),
                "kpi": context.get("kpi", {}),
                "readiness": context.get("readiness", {}),
                "instruction": (
                    "Generate a production-grade prompt optimized for LLM use. "
                    "Remove duplicate facts, compress metadata, preserve business meaning, "
                    "include PII guidance and SQL/RAG/agent safety constraints, and return only the final prompt text."
                ),
            }
        )
        return payload

    @staticmethod
    def _evaluation_metrics(context: dict[str, Any], artifact_content: str) -> dict[str, float]:
        """Compute simple trace metrics for generated prompt artifacts."""
        semantic = context.get("semantic") or {}
        embeddings = context.get("embeddings") or {}
        table_count = int(context.get("table_count", 0) or 0)
        schema_count = int(context.get("schema_count", 0) or 0)

        completeness_score = 0.0
        completeness_score += 0.35 if artifact_content.strip() else 0.0
        completeness_score += 0.25 if semantic.get("business_summary") else 0.0
        completeness_score += 0.20 if semantic.get("business_domain") else 0.0
        completeness_score += 0.20 if table_count > 0 else 0.0

        coverage_base = table_count + schema_count
        coverage_score = 0.0
        if coverage_base > 0:
            coverage_score = min(1.0, coverage_base / max(1, coverage_base + 3))
        if embeddings.get("indexed_tables"):
            coverage_score = min(1.0, coverage_score + 0.15)

        confidence_score = 0.0
        if semantic.get("confidence_score") is not None:
            confidence_score = max(0.0, min(1.0, float(semantic.get("confidence_score") or 0.0)))
        elif artifact_content.strip():
            confidence_score = 0.6

        return {
            "completeness_score": round(min(1.0, completeness_score), 3),
            "coverage_score": round(min(1.0, coverage_score), 3),
            "confidence_score": round(min(1.0, confidence_score), 3),
        }

    async def list_templates(self) -> list[dict[str, Any]]:
        templates = []
        for prompt_path in self.registry.list_prompts():
            if "/" in prompt_path:
                category, prompt_id = prompt_path.split("/", 1)
            else:
                category, prompt_id = None, prompt_path
            template = self.registry.load_prompt(prompt_id, category=category)
            templates.append(
                {
                    "id": template.get("id", prompt_id),
                    "name": template.get("name", prompt_id),
                    "description": template.get("description", ""),
                    "category": template.get("metadata", {}).get("category", "system"),
                    "version": str(template.get("version", "1.0")),
                    "language": template.get("language", "English"),
                    "path": f"app/prompts/{category + '/' if category else ''}{prompt_id}.yaml",
                }
            )
        return templates

    def prompt_inventory_report(self) -> list[dict[str, Any]]:
        consumers = {
            "semantic/database_analysis": "app.services.database_semantic_service",
            "semantic/pii_classification": "app.services.column_semantic_service",
            "relationship/relationship_discovery": "app.schema_engine.relationship_graph",
            "relationship/business_relationship_analysis": "app.schema_engine.relationship_graph",
            "kpi/kpi_discovery": "app.services.kpi_intelligence_service",
            "readiness/readiness_assessment": "app.services.readiness_service",
            "readiness/governance_readiness": "app.services.readiness_service",
            "system/database_context": "app.services.prompt_studio_service",
            "system/rag_context": "app.services.prompt_studio_service",
            "system/system_prompt": "app.services.prompt_studio_service",
            "system/agent_context": "app.services.prompt_studio_service",
            "system/text_to_sql": "app.services.prompt_studio_service",
        }
        inventory: list[dict[str, Any]] = []
        for prompt_path in self.registry.list_prompts():
            category, prompt_id = prompt_path.split("/", 1) if "/" in prompt_path else ("", prompt_path)
            consumer = consumers.get(prompt_path) or consumers.get(prompt_id) or "unknown"
            inventory.append(
                {
                    "prompt": prompt_id,
                    "category": category,
                    "executed": consumer != "unknown",
                    "loaded_only": consumer == "unknown",
                    "consumer": consumer,
                }
            )
        return inventory

    async def preview_artifact(self, database_id: int, artifact_type: str) -> PromptStudioArtifact:
        if not package_is_enabled("agent"):
            raise ValueError("Prompt Studio package is disabled by registry")
        context = await self._build_context(database_id)
        package = await self._generate_context_package(artifact_type, context)
        return PromptStudioArtifact(
            artifact_type=package.artifact_type,
            template_id=package.prompt_id,
            prompt_version=package.prompt_version,
            model_name=package.model_name,
            filename=package.filename,
            mime=package.mime,
            content=package.content,
            generated_at=package.generated_at,
            manifest=package.manifest,
        )

    async def generate_artifacts(self, database_id: int) -> list[dict[str, Any]]:
        if not package_is_enabled("agent"):
            raise ValueError("Prompt Studio package is disabled by registry")
        context = await self._build_context(database_id)
        generated: list[dict[str, Any]] = []

        for artifact_type in self._artifact_order():
            package = await self._generate_context_package(artifact_type.value, context)
            generated.append(
                {
                    "artifact_type": package.artifact_type.value,
                    "template_id": package.prompt_id,
                    "prompt_id": package.prompt_id,
                    "prompt_version": package.prompt_version,
                    "model_name": package.model_name,
                    "filename": package.manifest.get("filename", package.filename) if package.manifest else package.filename,
                    "mime": package.mime,
                    "content": package.content,
                    "generated_at": package.generated_at,
                    "context_quality_score": package.context_quality_score,
                    "governance_coverage": package.governance_coverage,
                    "pii_coverage": package.pii_coverage,
                    "manifest": package.manifest,
                }
            )

        return generated

    async def generate_prompt(
        self,
        database_id: int,
        artifact_type: str,
        template_id: str = "default",
    ) -> GeneratedPromptResult:
        if not package_is_enabled("agent"):
            raise ValueError("Prompt Studio package is disabled by registry")

        context = await self._build_context(database_id)
        artifact = self._artifact_enum(artifact_type)
        prompt_id = template_id if template_id and template_id != "default" else self._template_id_for(artifact_type)
        generation_context = self._assemble_generation_context(context, prompt_id)

        rendered = self.registry.render_prompt(prompt_id, generation_context, category="system")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="prompt_studio",
            artifact_type=artifact.value,
            prompt_id=prompt_id,
            prompt_version="1.0",
            database_id=database_id,
            database_name=context["database_name"],
            model_name=settings.azure_openai_deployment or "azure_openai",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an enterprise prompt engineer. Produce optimized prompts for downstream AI systems. "
                        "Use the supplied template and intelligence context. Return only the final prompt text."
                    ),
                },
                {
                    "role": "user",
                    "content": "\n\n".join(
                        [
                            f"Template ID: {prompt_id}",
                            f"Artifact Type: {artifact.value}",
                            f"Template:\n{rendered.system_message}\n{rendered.user_prompt}",
                            f"Context:\n{self._safe_json(generation_context)}",
                        ]
                    ),
                },
            ],
            request_kwargs={"max_completion_tokens": 2400},
            completeness_score=max(0.25, self._compute_quality(generation_context)["context_quality_score"]),
            coverage_score=self._compute_quality(generation_context)["governance_coverage"],
            confidence_score=self._compute_quality(generation_context)["pii_coverage"],
            extra_metadata={
                "feature": "prompt_studio_generate",
                "prompt_name": prompt_id,
                "artifact_type": artifact.value,
                "database_id": database_id,
            },
        )

        content = (result.content or "").strip()
        if not content:
            raise ValueError(f"Azure OpenAI returned empty content for {artifact.value}")

        mime = self._mime_for(artifact)
        filename = self._filename_for(artifact)
        saved = await self.artifact_service.record_artifact(
            database_id,
            artifact,
            content,
            mime=mime,
            extension=self._extension_for(artifact),
            schema_hash_payload={
                "artifact_type": artifact.value,
                "content": content,
                "database_id": database_id,
                "prompt_id": prompt_id,
                "prompt_version": "1.0",
                "model_name": result.model_name,
            },
            prompt_id=prompt_id,
            prompt_version="1.0",
            model_name=result.model_name,
        )

        return GeneratedPromptResult(
            artifact_type=artifact,
            prompt_id=prompt_id,
            prompt_version="1.0",
            model_name=result.model_name,
            content=content,
            filename=filename,
            generated_at=result.generated_at,
            trace_id=result.trace_id,
            confidence_score=self._compute_quality(generation_context)["confidence_score"],
            manifest=saved,
        )

    async def download_artifact(self, database_id: int, artifact_type: str) -> PromptStudioArtifact:
        if not package_is_enabled("agent"):
            raise ValueError("Prompt Studio package is disabled by registry")
        latest = await self._latest_manifest(database_id, artifact_type)
        if latest:
            content = Path(latest.artifact_path).read_text(encoding="utf-8")
            return PromptStudioArtifact(
                artifact_type=latest.artifact_type,
                template_id=self._template_id_for(artifact_type),
                prompt_version=latest.prompt_version or "1.0",
                model_name=latest.model_name or "template-engine",
                filename=Path(latest.artifact_path).name,
                mime=self._mime_for(artifact_type),
                content=content,
                generated_at=latest.generated_at,
                manifest=self._manifest_dict(latest),
            )
        return await self.preview_artifact(database_id, artifact_type)

    async def download_bundle(self, database_id: int) -> dict[str, Any]:
        if not package_is_enabled("agent"):
            raise ValueError("Prompt Studio package is disabled by registry")
        artifacts = []
        artifact_payloads = []
        for artifact_type in self._artifact_order():
            artifact = await self.download_artifact(database_id, artifact_type.value)
            artifact_payloads.append(
                {
                    "artifact_type": artifact.artifact_type.value,
                    "template_id": artifact.template_id,
                    "prompt_id": artifact.template_id,
                    "prompt_version": artifact.prompt_version,
                    "model_name": artifact.model_name,
                    "filename": artifact.filename,
                    "mime": artifact.mime,
                    "content": artifact.content,
                    "generated_at": artifact.generated_at.isoformat(),
                    "manifest": artifact.manifest,
                }
            )
            artifacts.append(artifact)

        bundle = {
            "database_id": database_id,
            "generated_at": now_utc().isoformat(),
            "artifacts": artifact_payloads,
        }
        return {
            "database_id": database_id,
            "bundle_filename": f"prompt_studio_bundle_{database_id}.json",
            "bundle_mime": "application/json",
            "content": json.dumps(bundle, indent=2, default=str),
            "artifacts": [
                {
                    "database_id": database_id,
                    "artifact_type": artifact.artifact_type.value,
                    "prompt_id": artifact.template_id,
                    "prompt_version": artifact.prompt_version,
                    "model_name": artifact.model_name,
                    "filename": artifact.filename,
                    "mime": artifact.mime,
                    "content": artifact.content,
                    "manifest": artifact.manifest,
                    "generated_at": artifact.generated_at,
                }
                for artifact in artifacts
            ],
            "message": "Prompt Studio bundle generated successfully.",
        }

    async def _build_context(self, database_id: int) -> dict[str, Any]:
        database = await self._fetch_database(database_id)
        semantic = await self._fetch_semantic(database_id)
        semantic_package = await self._fetch_semantic_package(database_id)
        tables = await self._fetch_tables(database_id)
        pii_map = await self._fetch_pii_map(database_id)
        governance_summary = await ColumnSemanticService(self.db).governance_summary(database_id)
        governance_packages = await self._fetch_governance_packages(database_id)
        relationship_packages = await self._fetch_relationship_packages(database_id)
        kpi_summary = await self._fetch_kpi_summary(database_id)
        relationship_intelligence = self._relationship_intelligence_from_packages(relationship_packages)
        try:
            embedding_status = await EmbeddingEngine(self.db).get_embedding_status(database_id)
        except Exception:
            embedding_status = {
                "indexed_tables": 0,
                "vectors_total": 0,
                "embedding_model": "",
                "qdrant_health": False,
                "collections": [],
            }
        try:
            from app.services.readiness_service import ReadinessService

            readiness = await ReadinessService(self.db).get_or_compute(database_id)
            readiness_payload = {
                "overall_score": readiness.overall_score,
                "category_scores": readiness.category_scores,
                "readiness_status": readiness.readiness_status.value,
                "missing_stages": readiness.missing_stages,
                "remediation_hints": readiness.remediation_hints,
            }
        except Exception:
            readiness_payload = {}

        schema_count = len(database.schemas or [])
        table_count = len(tables)
        column_count = sum(len(table.columns or []) for table in tables)
        relationship_count = sum(len(table.relationships_from or []) for table in tables)

        semantic_payload = {
            "business_domain": semantic.business_domain if semantic else None,
            "business_summary": semantic.business_summary if semantic else None,
            "analysis_notes": semantic.analysis_notes if semantic else None,
            "confidence_score": semantic.confidence_score if semantic else 0.0,
            "generation_status": semantic.generation_status.value if semantic else "not_generated",
            "key_entities": semantic.key_entities if semantic else [],
            "business_glossary": semantic.business_glossary if semantic else [],
            "suggested_use_cases": semantic.suggested_use_cases if semantic else [],
            "semantic_package": self._semantic_package_to_dict(semantic_package) if semantic_package else {},
        }

        table_payloads = []
        column_payloads = []
        for table in tables:
            relevant_columns = []
            for column in sorted(table.columns or [], key=lambda c: c.ordinal_position or 0):
                semantic_row = pii_map.get(column.id)
                column_info = {
                    "column_id": column.id,
                    "schema_name": table.schema.name,
                    "table_name": table.name,
                    "name": column.name,
                    "data_type": column.data_type,
                    "description": column.description,
                    "is_pii": bool(semantic_row and semantic_row.is_pii),
                    "pii_type": semantic_row.pii_type if semantic_row else None,
                    "risk_level": semantic_row.risk_level if semantic_row else None,
                    "confidence_score": semantic_row.confidence_score if semantic_row else 0.0,
                }
                column_payloads.append(column_info)
                if len(relevant_columns) < 8:
                    relevant_columns.append(column.name)
            table_payloads.append(
                {
                    "schema_name": table.schema.name,
                    "table_name": table.name,
                    "table_type": table.table_type.value,
                    "relevant_columns": relevant_columns,
                    "semantic_status": semantic.generation_status.value if semantic else "not_generated",
                    "embedding_status": table.embedding.embedding_status.value if table.embedding else "pending",
                }
            )

        collection_names = [item.get("collection_name", "") for item in embedding_status.get("collections", [])]
        embeddings_payload = {
            "indexed_tables": embedding_status.get("indexed_tables", 0),
            "vector_count": embedding_status.get("vectors_total", 0),
            "embedding_model": embedding_status.get("embedding_model", ""),
            "qdrant_health": embedding_status.get("qdrant_health", False),
            "collection_names": [name for name in collection_names if name],
        }

        return {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "generated_at": now_utc().isoformat(),
            "schema_count": schema_count,
            "table_count": table_count,
            "column_count": column_count,
            "relationship_count": relationship_count,
            "semantic": semantic_payload,
            "relationship_intelligence": relationship_intelligence,
            "relationship_packages": [self._relationship_package_to_dict(row) for row in relationship_packages],
            "readiness": readiness_payload,
            "embeddings": embeddings_payload,
            "kpi": kpi_summary,
            "tables": table_payloads,
            "columns": column_payloads,
            "governance": {
                **governance_summary,
                "pii_coverage": governance_summary.get("pii_identified_coverage", 0.0),
                "prompt_protection_enabled": governance_summary.get("prompt_protection_enabled", False),
                "embedding_protection_enabled": governance_summary.get("embedding_protection_enabled", False),
            },
            "governance_packages": [self._governance_package_to_dict(row) for row in governance_packages],
        }

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(
                    DatabaseTable.columns
                ),
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(
                    DatabaseTable.embedding
                ),
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(
                    DatabaseTable.relationships_from
                ),
            )
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _fetch_semantic(self, database_id: int) -> Optional[DatabaseSemantic]:
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        return result.scalars().first()

    async def _fetch_semantic_package(self, database_id: int) -> SemanticPackage | None:
        result = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))
        return result.scalars().first()

    async def _fetch_pii_map(self, database_id: int) -> dict[int, ColumnSemantic]:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.database_id == database_id)
        )
        return {row.column_id: row for row in result.scalars().all()}

    @staticmethod
    def _relationship_intelligence_from_packages(packages: list[RelationshipPackage]) -> dict[str, Any]:
        if not packages:
            return {}
        first = packages[0]
        return {
            "entity_graph": first.entity_graph or [],
            "business_process_flows": first.business_process_flows or [],
            "hidden_relationships": first.hidden_relationships or [],
            "upstream_dependencies": first.upstream_dependencies or [],
            "downstream_dependencies": first.downstream_dependencies or [],
            "lifecycle_flows": first.lifecycle_flows or [],
            "cluster_summary": first.cluster_summary or "",
            "cluster_confidence": first.confidence_score or 0.0,
            "domain_name": first.domain_name or "",
            "prompt_id": first.prompt_id or "",
            "prompt_version": first.prompt_version or "",
            "model_name": first.model_name or "",
        }

    async def _fetch_tables(self, database_id: int) -> list[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .join(DatabaseSchema)
            .options(
                selectinload(DatabaseTable.schema),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.embedding),
                selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return result.scalars().unique().all()

    async def _fetch_governance_packages(self, database_id: int) -> list[GovernancePackage]:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.database_id == database_id)
        )
        return list(result.scalars().all())

    async def _fetch_relationship_packages(self, database_id: int) -> list[RelationshipPackage]:
        result = await self.db.execute(
            select(RelationshipPackage).where(RelationshipPackage.database_id == database_id)
        )
        return list(result.scalars().all())

    async def _fetch_kpi_summary(self, database_id: int) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(KPIIntelligence).where(KPIIntelligence.database_id == database_id)
            )
            rows = list(result.scalars().all())
        except Exception as exc:
            logger.warning("KPI summary unavailable for database_id=%s: %s", database_id, exc)
            return {"kpi_count": 0, "kpis": [], "unavailable": True}
        return {
            "kpi_count": len(rows),
            "kpis": [
                {
                    "name": row.name,
                    "formula": row.formula,
                    "business_meaning": row.business_meaning,
                    "confidence": row.confidence,
                }
                for row in rows[:50]
            ],
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

    async def _generate_context_package(self, artifact_type: str, context: dict[str, Any]) -> ContextPackageResult:
        artifact = self._artifact_enum(artifact_type)
        payload = self._assemble_context_payload(artifact, context)
        quality = self._compute_quality(payload)
        prompt_id = self._template_id_for(artifact_type)
        prompt_version = "1.0"
        model_name = settings.azure_openai_deployment or "azure_openai"
        rendered = self.registry.render_prompt(prompt_id, payload, category="system")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="prompt_studio",
            artifact_type=artifact.value,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            database_id=context["database_id"],
            database_name=context["database_name"],
            model_name=model_name,
            messages=[
                {"role": "system", "content": rendered.system_message},
                {"role": "user", "content": rendered.user_prompt},
            ],
            request_kwargs={"max_completion_tokens": 1800},
            completeness_score=quality["context_quality_score"],
            coverage_score=quality["governance_coverage"],
            confidence_score=quality["pii_coverage"],
            extra_metadata={
                "feature": "prompt_studio",
                "prompt_name": prompt_id,
                "artifact_type": artifact.value,
                "database_id": context["database_id"],
                "model_name": model_name,
            },
        )
        content = (result.content or "").strip()
        if not content:
            raise ValueError(f"Azure OpenAI returned empty content for {artifact.value}")
        mime = self._mime_for(artifact)
        filename = self._filename_for(artifact)
        saved = await self.artifact_service.record_artifact(
            context["database_id"],
            artifact,
            content,
            mime=mime,
            extension=self._extension_for(artifact),
            schema_hash_payload={
                "artifact_type": artifact.value,
                "content": content,
                "database_id": context["database_id"],
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "model_name": result.model_name,
            },
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=result.model_name,
        )
        return ContextPackageResult(
            artifact_type=artifact,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=result.model_name,
            content=content,
            mime=mime,
            filename=filename,
            context_quality_score=quality["context_quality_score"],
            governance_coverage=quality["governance_coverage"],
            pii_coverage=quality["pii_coverage"],
            generated_at=result.generated_at,
            manifest=saved,
        )

    async def _latest_manifest(self, database_id: int, artifact_type: str):
        from app.models.artifact_manifest import ArtifactManifest
        from sqlalchemy import desc

        result = await self.db.execute(
            select(ArtifactManifest)
            .where(
                ArtifactManifest.database_id == database_id,
                ArtifactManifest.artifact_type == self._artifact_enum(artifact_type),
            )
            .order_by(desc(ArtifactManifest.version))
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    def _artifact_order() -> list[ArtifactType]:
        enabled_artifacts = set(package_artifacts("semantic")) | set(package_artifacts("rag")) | set(package_artifacts("agent")) | set(package_artifacts("text_to_sql"))
        ordered = [ArtifactType.resolve(name) for name in dict.fromkeys(enabled_artifacts) if name]
        preferred = [
            ArtifactType.database_context,
            ArtifactType.system_prompt,
            ArtifactType.rag_context,
            ArtifactType.agent_context,
            ArtifactType.text_to_sql_context,
        ]
        return [artifact for artifact in preferred if artifact.value in enabled_artifacts or artifact.name in enabled_artifacts] or ordered

    @staticmethod
    def _artifact_enum(value: str | ArtifactType) -> ArtifactType:
        return ArtifactType.resolve(value)

    @staticmethod
    def _template_id_for(value: str) -> str:
        artifact_type = ArtifactType.resolve(value)
        mapping = {
            ArtifactType.database_context: "database_context",
            ArtifactType.system_prompt: "system_prompt",
            ArtifactType.rag_context: "rag_context",
            ArtifactType.agent_context: "agent_context",
            ArtifactType.text_to_sql_context: "text_to_sql",
        }
        return mapping[artifact_type]

    @staticmethod
    def _mime_for(value: str) -> str:
        artifact_type = ArtifactType.resolve(value)
        if artifact_type == ArtifactType.agent_context:
            return "application/json"
        return "text/markdown"

    @staticmethod
    def _extension_for(artifact_type: ArtifactType) -> str:
        if artifact_type == ArtifactType.agent_context:
            return ".json"
        return ".md"

    @staticmethod
    def _filename_for(artifact_type: ArtifactType) -> str:
        return artifact_type.value

    @staticmethod
    def _manifest_dict(item) -> dict[str, Any]:
        return {
            "id": item.id,
            "artifact_type": item.artifact_type.value,
            "version": item.version,
            "schema_hash": item.schema_hash,
            "prompt_id": item.prompt_id,
            "prompt_version": item.prompt_version,
            "model_name": item.model_name,
            "export_status": item.export_status.value,
            "artifact_path": item.artifact_path,
            "generated_at": item.generated_at,
        }
