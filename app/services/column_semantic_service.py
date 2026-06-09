"""Column semantic storage, AI PII classification, and readiness hooks."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    SemanticGenerationStatus,
)
from app.config.manager import get_config_manager
from app.services.ai_observability_service import AIObservabilityService
from app.config.prompts import get_prompt_registry

logger = logging.getLogger(__name__)


@dataclass
class PIIClassificationResult:
    is_pii: bool
    pii_type: str | None
    risk_level: str | None
    confidence_score: float
    classification_source: str
    review_status: str
    prompt_id: str
    prompt_version: str
    model_name: str
    classified_at: datetime
    metadata_fingerprint: str
    notes: str | None = None


class ColumnSemanticService:
    """AI-based column PII classification backed by column_semantics storage."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = get_prompt_registry()
        self.config = get_config_manager()

    def _risk_from_probability(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.6:
            return "medium"
        return "low"

    @staticmethod
    def _review_status_from_confidence(confidence: float) -> str:
        return "auto_approved" if confidence >= 0.8 else "needs_review"

    def _governance_config(self) -> dict[str, Any]:
        return self.config.get_semantic_rules().get("pii_classification", {})

    @staticmethod
    def _column_metadata_fingerprint(column: DatabaseColumn, table: DatabaseTable) -> str:
        parts = [
            table.schema.name,
            table.name,
            table.description or "",
            column.name,
            column.data_type,
            column.description or "",
        ]
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return digest[:32]

    def _classification_context(
        self,
        column: DatabaseColumn,
        table: DatabaseTable,
        database: ConnectedDatabase,
        semantic: DatabaseSemantic | None,
    ) -> dict[str, Any]:
        return {
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "schema_name": table.schema.name,
            "table_name": table.name,
            "table_description": table.description or "",
            "column_name": column.name,
            "column_description": column.description or "",
            "column_data_type": column.data_type,
            "semantic_summary": semantic.business_summary if semantic else "",
            "business_domain": semantic.business_domain if semantic else "",
            "analysis_notes": semantic.analysis_notes if semantic else "",
            "existing_business_glossary": semantic.business_glossary if semantic else [],
        }

    async def _fetch_database_semantic(self, database_id: int) -> DatabaseSemantic | None:
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_table_with_column(self, column_id: int) -> tuple[DatabaseColumn, DatabaseTable, ConnectedDatabase]:
        result = await self.db.execute(
            select(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .join(ConnectedDatabase)
            .where(DatabaseColumn.id == column_id)
        )
        column = result.scalars().first()
        if not column:
            raise ValueError(f"Column {column_id} not found")
        table = column.table
        database = table.schema.connected_database
        return column, table, database

    def _needs_classification(
        self,
        column: DatabaseColumn,
        table: DatabaseTable,
        existing: ColumnSemantic | None,
        force: bool,
    ) -> bool:
        if force or existing is None:
            return True
        fingerprint = self._column_metadata_fingerprint(column, table)
        return existing.metadata_fingerprint != fingerprint

    async def classify_column(self, column_id: int, force: bool = False) -> ColumnSemantic:
        column, table, database = await self._fetch_table_with_column(column_id)
        existing = await self.get_by_column_id(column_id)
        if existing and not self._needs_classification(column, table, existing, force):
            return existing

        semantic = await self._fetch_database_semantic(database.id)
        prompt_context = self._classification_context(column, table, database, semantic)
        prompt_cfg = self._governance_config()
        decision_rules = prompt_cfg.get("decision_rules", {})
        prompt_id = decision_rules.get("default_prompt_id", "pii_classification")
        model_name = settings.azure_openai_deployment or decision_rules.get("fallback_model_name", "azure_openai")
        prompt = self.registry.render_prompt(prompt_id, prompt_context, category="semantic")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="pii_governance",
            artifact_type="column_pii_classification",
            database_id=database.id,
            database_name=database.display_name or database.name,
            prompt_id=prompt.metadata.id,
            prompt_version=prompt.metadata.version,
            model_name=model_name,
            messages=[
                {
                    "role": "system",
                    "content": prompt.system_message
                    or "Sensitive fields identified as PII must be summarized, classified, masked, or redacted. Never expose raw sensitive values.",
                },
                {"role": "user", "content": prompt.user_prompt},
            ],
            request_kwargs={"response_format": {"type": "json_object"}, "max_completion_tokens": 800},
            completeness_score=1.0,
            coverage_score=1.0 if semantic else 0.5,
            confidence_score=0.0,
            extra_metadata={
                "classification_source": "llm",
                "column_name": column.name,
                "table_name": table.name,
                "schema_name": table.schema.name,
            },
        )

        fingerprint = self._column_metadata_fingerprint(column, table)
        classification = self._parse_classification(
            result.content or "",
            prompt.metadata.id,
            str(prompt.metadata.version),
            model_name,
            fingerprint,
        )
        row = await self._upsert_semantic(column, database.id, classification, result)
        return row

    def _parse_classification(
        self,
        response_text: str,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        metadata_fingerprint: str,
    ) -> PIIClassificationResult:
        payload: dict[str, Any] = {}
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            payload = json.loads(cleaned)
        except Exception:
            logger.warning("PII classification response was not valid JSON")

        is_pii = bool(payload.get("is_pii", False))
        pii_type = payload.get("pii_type")
        if not is_pii or pii_type in (None, "", "null"):
            pii_type = None
        confidence = float(payload.get("confidence_score", 0.0))
        risk_level = payload.get("risk_level") or self._risk_from_probability(confidence)
        return PIIClassificationResult(
            is_pii=is_pii,
            pii_type=pii_type,
            risk_level=risk_level if is_pii else "low",
            confidence_score=max(0.0, min(1.0, confidence)),
            classification_source=str(payload.get("classification_source", "llm")),
            review_status=str(
                payload.get("review_status", self._review_status_from_confidence(confidence))
            ),
            prompt_id=str(payload.get("prompt_id", prompt_id)),
            prompt_version=str(payload.get("prompt_version", prompt_version)),
            model_name=str(payload.get("model_name", model_name)),
            classified_at=datetime.now(timezone.utc),
            metadata_fingerprint=metadata_fingerprint,
            notes=payload.get("notes"),
        )

    async def _upsert_semantic(
        self,
        column: DatabaseColumn,
        database_id: int,
        classification: PIIClassificationResult,
        ai_result: Any,
    ) -> ColumnSemantic:
        row = await self.get_by_column_id(column.id)
        if row is None:
            row = ColumnSemantic(column_id=column.id, database_id=database_id)
            self.db.add(row)
        row.business_name = column.name.replace("_", " ").title()
        row.business_description = column.description or ""
        row.column_category = "pii" if classification.is_pii else "non_pii"
        row.table_category = column.table.table_type.value if getattr(column, "table", None) else None
        row.is_pii = classification.is_pii
        row.pii_type = classification.pii_type
        row.risk_level = classification.risk_level
        row.confidence_score = classification.confidence_score
        row.prompt_id = classification.prompt_id
        row.prompt_version = classification.prompt_version
        row.model_name = classification.model_name
        row.metadata_fingerprint = classification.metadata_fingerprint
        row.generated_at = classification.classified_at
        row.updated_at = classification.classified_at
        await self.db.flush()
        return row

    async def generate_for_database(self, database_id: int, force: bool = False) -> list[ColumnSemantic]:
        """Classify new or changed columns; skip unchanged records unless force=True."""
        database = await self._fetch_database(database_id)
        semantic = await self._fetch_database_semantic(database_id)
        if semantic is None or semantic.generation_status != SemanticGenerationStatus.completed:
            logger.info(
                "Skipping PII generation for database %s until semantic intelligence is completed",
                database_id,
            )
            return await self.get_by_database_id(database_id)

        columns = await self._get_columns_for_database(database_id)
        current_ids = {column.id for column in columns}
        await self._cleanup_orphans(database_id, current_ids)

        column_count = len(columns)
        observability = AIObservabilityService()
        with observability.observe(
            module="column_semantics",
            artifact_type="column_semantic_batch",
            prompt_id="pii_classification",
            prompt_version="1.0",
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name=settings.azure_openai_deployment or "azure_openai",
            completeness_score=1.0 if column_count > 0 else 0.0,
            coverage_score=min(1.0, column_count / 100.0) if column_count > 0 else 0.0,
            confidence_score=0.5 if column_count > 0 else 0.0,
            extra_metadata={
                "column_count": column_count,
                "readiness_category": "governance",
                "force": force,
            },
        ):
            results: list[ColumnSemantic] = []
            for column in columns:
                try:
                    results.append(await self.classify_column(column.id, force=force))
                except Exception as exc:
                    logger.error(
                        "PII classification failed for column_id=%s: %s",
                        column.id,
                        exc,
                        exc_info=True,
                    )
            return results

    async def get_by_database_id(self, database_id: int) -> list[ColumnSemantic]:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.database_id == database_id)
        )
        return list(result.scalars().all())

    async def get_for_database(self, database_id: int) -> list[ColumnSemantic]:
        return await self.get_by_database_id(database_id)

    async def rescan_database(self, database_id: int, force: bool = False) -> list[ColumnSemantic]:
        return await self.generate_for_database(database_id, force=force)

    async def get_by_column_id(self, column_id: int) -> ColumnSemantic | None:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.column_id == column_id)
        )
        return result.scalar_one_or_none()

    async def get_pii_map(self, database_id: int) -> dict[int, ColumnSemantic]:
        rows = await self.get_by_database_id(database_id)
        return {row.column_id: row for row in rows}

    async def create(self, semantic: ColumnSemantic) -> ColumnSemantic:
        self.db.add(semantic)
        await self.db.commit()
        await self.db.refresh(semantic)
        return semantic

    async def _cleanup_orphans(self, database_id: int, current_column_ids: set[int]) -> None:
        if not current_column_ids:
            await self.db.execute(
                delete(ColumnSemantic).where(ColumnSemantic.database_id == database_id)
            )
            return
        existing = await self.get_by_database_id(database_id)
        for row in existing:
            if row.column_id not in current_column_ids:
                await self.db.delete(row)

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        result = await self.db.execute(
            select(ConnectedDatabase).where(ConnectedDatabase.id == database_id)
        )
        database = result.scalars().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _count_columns(self, database_id: int) -> int:
        result = await self.db.execute(
            select(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return len(result.scalars().all())

    async def _get_columns_for_database(self, database_id: int) -> list[DatabaseColumn]:
        result = await self.db.execute(
            select(DatabaseColumn)
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().all())
