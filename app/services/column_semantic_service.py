"""Column semantic storage, PII classification, and readiness hooks."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.column_semantic import ColumnSemantic
from app.models.metadata import ConnectedDatabase, DatabaseColumn, DatabaseSchema, DatabaseSemantic, DatabaseTable
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
    notes: str | None = None


class ColumnSemanticService:
    """Read and scaffold column semantic records with observability hooks."""

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

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    def _governance_config(self) -> dict[str, Any]:
        return self.config.get_semantic_rules().get("pii_classification", {})

    def _extract_config_signals(self, text: str) -> tuple[list[str], list[str]]:
        config = self._governance_config()
        categories = config.get("categories", {}) or {}
        matched_labels: list[str] = []
        matched_types: list[str] = []
        lowered = text.lower()
        for category in categories.values():
            labels = category.get("labels", []) or []
            pii_types = category.get("pii_types", []) or []
            if any(label.lower() in lowered for label in labels):
                matched_labels.extend(labels)
                matched_types.extend(pii_types)
        return list(dict.fromkeys(matched_labels)), list(dict.fromkeys(matched_types))

    def _classification_context(self, column: DatabaseColumn, table: DatabaseTable, database: ConnectedDatabase, semantic: DatabaseSemantic | None) -> dict[str, Any]:
        description = " ".join(
            part
            for part in [
                column.name,
                column.description or "",
                table.name,
                table.description or "",
                table.schema.name,
                semantic.business_domain if semantic else "",
                semantic.business_summary if semantic else "",
                semantic.analysis_notes if semantic else "",
            ]
            if part
        )
        matched_labels, matched_types = self._extract_config_signals(description)
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
            "config_signals": matched_labels,
            "config_pii_types": matched_types,
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

    async def classify_column(self, column_id: int, force: bool = False) -> ColumnSemantic:
        column, table, database = await self._fetch_table_with_column(column_id)
        existing = await self.get_by_column_id(column_id)
        if existing and not force:
            return existing

        semantic = await self._fetch_database_semantic(database.id)
        prompt_context = self._classification_context(column, table, database, semantic)
        prompt_cfg = self._governance_config()
        prompt_id = prompt_cfg.get("decision_rules", {}).get("default_prompt_id", "pii_classification")
        prompt_version = str(prompt_cfg.get("decision_rules", {}).get("default_prompt_version", "1.0"))
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
            model_name=prompt_cfg.get("decision_rules", {}).get("fallback_model_name", "azure_openai"),
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
                "config_signals": prompt_context["config_signals"],
                "column_name": column.name,
                "table_name": table.name,
            },
        )

        classification = self._parse_classification(result.content or "", column, table, prompt_context)
        row = await self._upsert_semantic(column, database.id, classification, result)
        return row

    def _parse_classification(
        self,
        response_text: str,
        column: DatabaseColumn,
        table: DatabaseTable,
        prompt_context: dict[str, Any],
    ) -> PIIClassificationResult:
        config = self._governance_config()
        matched_types = prompt_context.get("config_pii_types", []) or []
        default_conf = 0.2 if not matched_types else min(0.95, 0.45 + len(matched_types) * 0.1)
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(response_text.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            logger.debug("PII classification response was not JSON; falling back to config signals")

        is_pii = bool(payload.get("is_pii", bool(matched_types)))
        pii_type = payload.get("pii_type") or (matched_types[0] if matched_types else ("Personal Data" if is_pii else None))
        risk_level = payload.get("risk_level") or self._risk_from_probability(float(payload.get("confidence_score", default_conf)))
        confidence = float(payload.get("confidence_score", default_conf))
        return PIIClassificationResult(
            is_pii=is_pii,
            pii_type=pii_type,
            risk_level=risk_level,
            confidence_score=max(0.0, min(1.0, confidence)),
            classification_source=payload.get("classification_source", "llm+config"),
            review_status=payload.get("review_status", self._review_status_from_confidence(confidence)),
            prompt_id=payload.get("prompt_id", config.get("decision_rules", {}).get("default_prompt_id", "pii_classification")),
            prompt_version=str(payload.get("prompt_version", config.get("decision_rules", {}).get("default_prompt_version", "1.0"))),
            model_name=payload.get("model_name", config.get("decision_rules", {}).get("fallback_model_name", "azure_openai")),
            classified_at=datetime.now(timezone.utc),
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
        row.generated_at = classification.classified_at
        row.updated_at = classification.classified_at
        await self.db.flush()
        return row

    async def generate_for_database(self, database_id: int) -> list[ColumnSemantic]:
        """
        Future AI generation entrypoint for column-level semantics.

        The service currently returns the persisted column semantic records while
        emitting a trace so PII/KPI generation can reuse the same observability
        path once model-backed generation is added.
        """
        database = await self._fetch_database(database_id)
        column_count = await self._count_columns(database_id)
        completeness_score = 1.0 if column_count > 0 else 0.0
        coverage_score = min(1.0, column_count / 100.0) if column_count > 0 else 0.0
        confidence_score = 0.5 if column_count > 0 else 0.0
        observability = AIObservabilityService()
        with observability.observe(
            module="column_semantics",
            artifact_type="column_semantic_batch",
            prompt_id="pii_governance",
            prompt_version="1",
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name="deterministic",
            completeness_score=completeness_score,
            coverage_score=coverage_score,
            confidence_score=confidence_score,
            extra_metadata={
                "column_count": column_count,
                "readiness_category": "governance",
            },
        ):
            columns = await self._get_columns_for_database(database_id)
            results = []
            for column in columns:
                try:
                    results.append(await self.classify_column(column.id, force=True))
                except Exception as exc:
                    logger.error("PII classification failed for column_id=%s: %s", column.id, exc, exc_info=True)
            return results

    async def get_by_database_id(self, database_id: int) -> list[ColumnSemantic]:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.database_id == database_id)
        )
        return list(result.scalars().all())

    async def get_for_database(self, database_id: int) -> list[ColumnSemantic]:
        return await self.get_by_database_id(database_id)

    async def rescan_database(self, database_id: int) -> list[ColumnSemantic]:
        columns = await self._get_columns_for_database(database_id)
        results: list[ColumnSemantic] = []
        for column in columns:
            results.append(await self.classify_column(column.id, force=True))
        return results

    async def get_by_column_id(self, column_id: int) -> ColumnSemantic | None:
        result = await self.db.execute(
            select(ColumnSemantic).where(ColumnSemantic.column_id == column_id)
        )
        return result.scalar_one_or_none()

    async def create(self, semantic: ColumnSemantic) -> ColumnSemantic:
        self.db.add(semantic)
        await self.db.commit()
        await self.db.refresh(semantic)
        return semantic

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
