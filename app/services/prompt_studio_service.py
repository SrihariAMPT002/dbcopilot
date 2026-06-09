"""
Prompt Studio artifact generation service.

Builds database-context artifacts from semantic intelligence, relationship
graph, metadata, and embedding metadata using YAML templates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.prompts import PromptRegistry, get_prompt_registry
from app.models.artifact_manifest import ArtifactType
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseSemantic, DatabaseTable
from app.services.ai_observability_service import AIObservabilityService
from app.schema_engine.embeddings import EmbeddingEngine
from app.schema_engine.relationship_graph import RelationshipGraphEngine
from app.services.artifact_service import ArtifactService
from app.utils import now_utc


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


class PromptStudioService:
    """Generate versioned Prompt Studio artifacts from shared metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry: PromptRegistry = get_prompt_registry()
        self.artifact_service = ArtifactService(db)

    @staticmethod
    def _sensitive_column_patterns() -> tuple[re.Pattern[str], ...]:
        return (
            re.compile(r".*(email|e-mail|mail).*", re.I),
            re.compile(r".*(password|passwd|secret|token|otp|auth).*", re.I),
            re.compile(r".*(ssn|social_security|national_id|passport|driver|license).*", re.I),
            re.compile(r".*(credit|card|iban|bank|account|routing|swift|tax).*", re.I),
            re.compile(r".*(health|medical|diagnosis|patient|regulatory|employee|customer).*", re.I),
        )

    @classmethod
    def _is_sensitive_field(cls, name: str, risk_level: str | None = None) -> bool:
        if risk_level and risk_level.lower() in {"high", "critical"}:
            return True
        return any(pattern.match(name or "") for pattern in cls._sensitive_column_patterns())

    @staticmethod
    def _redact_text(text: str) -> str:
        return text

    @classmethod
    def _redact_context(cls, context: dict[str, Any]) -> dict[str, Any]:
        redacted = json.loads(json.dumps(context, default=str))
        semantic = redacted.get("semantic") or {}
        columns = redacted.get("columns") or []
        for column in columns:
            if cls._is_sensitive_field(column.get("name", ""), column.get("risk_level")):
                column["name"] = "[PII REDACTED]"
                if column.get("description"):
                    column["description"] = "[PII REDACTED]"
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
        if artifact_type in {"database_context.md", "system_prompt.md", "rag_context.md", "agent_context.json", "text_to_sql_context.md"}:
            return self._redact_context(context)
        return context

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
        for prompt_id in self.registry.list_prompts("system"):
            template = self.registry.load_prompt(prompt_id, category="system")
            templates.append(
                {
                    "id": template.get("id", prompt_id),
                    "name": template.get("name", prompt_id),
                    "description": template.get("description", ""),
                    "category": template.get("metadata", {}).get("category", "system"),
                    "version": str(template.get("version", "1.0")),
                    "language": template.get("language", "English"),
                    "path": f"app/prompts/system/{prompt_id}.yml",
                }
            )
        return templates

    async def preview_artifact(self, database_id: int, artifact_type: str) -> PromptStudioArtifact:
        context = await self._build_context(database_id)
        return self._render_artifact(artifact_type, context)

    async def generate_artifacts(self, database_id: int) -> list[dict[str, Any]]:
        context = await self._build_context(database_id)
        generated: list[dict[str, Any]] = []
        observability = AIObservabilityService()

        for artifact_type in self._artifact_order():
            artifact = self._render_artifact(artifact_type.value, context)
            metrics = self._evaluation_metrics(context, artifact.content)
            with observability.observe(
                module="prompt_studio",
                artifact_type=artifact.artifact_type.value,
                prompt_id=artifact.template_id,
                prompt_version=artifact.prompt_version,
                database_id=database_id,
                database_name=context["database_name"],
                model_name=artifact.model_name,
                completeness_score=metrics["completeness_score"],
                coverage_score=metrics["coverage_score"],
                confidence_score=metrics["confidence_score"],
                extra_metadata={
                    "template_used": artifact.template_id,
                    "artifact_type": artifact.artifact_type.value,
                    "prompt_version": artifact.prompt_version,
                },
            ):
                saved = await self.artifact_service.record_artifact(
                    database_id,
                    artifact.artifact_type,
                    artifact.content,
                    mime=artifact.mime,
                    extension=self._extension_for(artifact.artifact_type),
                    schema_hash_payload={
                        "artifact_type": artifact.artifact_type.value,
                        "content": artifact.content,
                        "database_id": database_id,
                    },
                    prompt_id=artifact.template_id,
                    prompt_version=artifact.prompt_version,
                    model_name=artifact.model_name,
                )
            artifact.manifest = saved
            generated.append(
                {
                    "artifact_type": artifact.artifact_type.value,
                    "template_id": artifact.template_id,
                    "prompt_id": artifact.template_id,
                    "prompt_version": artifact.prompt_version,
                    "model_name": artifact.model_name,
                    "filename": saved.get("filename", artifact.filename),
                    "mime": artifact.mime,
                    "content": artifact.content,
                    "generated_at": artifact.generated_at,
                    "manifest": saved,
                }
            )

        return generated

    async def download_artifact(self, database_id: int, artifact_type: str) -> PromptStudioArtifact:
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
        tables = await self._fetch_tables(database_id)
        try:
            relationship_graph = await RelationshipGraphEngine(self.db).get_relationship_graph(database_id)
        except Exception:
            relationship_graph = None
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
        }

        table_payloads = []
        for table in tables:
            relevant_columns = [
                column.name
                for column in sorted(table.columns or [], key=lambda c: c.ordinal_position or 0)[:8]
            ]
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
            "relationship_graph": relationship_graph,
            "embeddings": embeddings_payload,
            "tables": table_payloads,
        }

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(selectinload(ConnectedDatabase.schemas))
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

    def _render_artifact(self, artifact_type: str, context: dict[str, Any]) -> PromptStudioArtifact:
        template_id = self._template_id_for(artifact_type)
        template = self.registry.load_prompt(template_id, category="system")
        rendered = self.registry.render_prompt(template_id, context, category="system")
        content = rendered.user_prompt.strip()
        mime = self._mime_for(artifact_type)
        return PromptStudioArtifact(
            artifact_type=self._artifact_enum(artifact_type),
            template_id=template_id,
            prompt_version=str(template.get("version", rendered.metadata.version or "1.0")),
            model_name="template-engine",
            filename=artifact_type,
            mime=mime,
            content=content,
            generated_at=now_utc(),
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
        return [
            ArtifactType.database_context,
            ArtifactType.system_prompt,
            ArtifactType.rag_context,
            ArtifactType.agent_context,
            ArtifactType.text_to_sql_context,
        ]

    @staticmethod
    def _artifact_enum(value: str) -> ArtifactType:
        mapping = {
            "database_context.md": ArtifactType.database_context,
            "system_prompt.md": ArtifactType.system_prompt,
            "rag_context.md": ArtifactType.rag_context,
            "agent_context.json": ArtifactType.agent_context,
            "text_to_sql_context.md": ArtifactType.text_to_sql_context,
        }
        return mapping[value]

    @staticmethod
    def _template_id_for(value: str) -> str:
        mapping = {
            "database_context.md": "database_context",
            "system_prompt.md": "system_prompt",
            "rag_context.md": "rag_context",
            "agent_context.json": "agent_context",
            "text_to_sql_context.md": "text_to_sql",
            # support raw names too
            "database_context": "database_context",
            "system_prompt": "system_prompt",
            "rag_context": "rag_context",
            "agent_context": "agent_context",
            "text_to_sql_context": "text_to_sql",
        }

        return mapping[value]

    @staticmethod
    def _mime_for(value: str) -> str:
        if value == "agent_context":
            return "application/json"
        return "text/markdown"

    @staticmethod
    def _extension_for(artifact_type: ArtifactType) -> str:
        if artifact_type == ArtifactType.agent_context:
            return ".json"
        return ".md"

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
