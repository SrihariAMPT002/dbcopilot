"""Column semantic storage, AI PII classification, and readiness hooks."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


def _log_stage_duration(stage: str, start: float, **fields) -> None:
    elapsed = time.monotonic() - start
    logger.info("%s completed in %.2fs | %s", stage, elapsed, ", ".join(f"{k}={v}" for k, v in fields.items()))


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

    def _governance_rulebook(self) -> dict[str, Any]:
        return self.config.get_governance_rulebook()

    @staticmethod
    def _compile_rule_patterns(rulebook: dict[str, Any]) -> dict[str, dict[str, Any]]:
        compiled: dict[str, dict[str, Any]] = {}
        categories = ((rulebook.get("pii_rules") or {}).get("categories") or {})
        for category, spec in categories.items():
            compiled[category] = {
                "label": spec.get("label", category),
                "patterns": [re.compile(str(pattern), re.I) for pattern in spec.get("patterns", [])],
                "synonyms": [str(item).lower() for item in spec.get("synonyms", [])],
                "risk_level": spec.get("risk_level"),
                "confidence_threshold": float(spec.get("confidence_threshold", 0.0)),
            }
        return compiled

    @classmethod
    def _rule_engine_match(
        cls,
        name: str,
        description: str | None = None,
        *,
        compiled_rules: dict[str, dict[str, Any]],
    ) -> tuple[bool, str | None, str | None, float]:
        haystack = f"{name} {description or ''}".lower()
        for pii_type, spec in compiled_rules.items():
            matched = any(pattern.search(haystack) for pattern in spec["patterns"]) or any(
                synonym in haystack for synonym in spec["synonyms"]
            )
            if matched:
                return True, pii_type, spec.get("risk_level") or "low", max(
                    0.99, float(spec.get("confidence_threshold", 0.0))
                )
        return False, None, None, 0.0

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

    def _table_classification_context(
        self,
        table: DatabaseTable,
        database: ConnectedDatabase,
        semantic: DatabaseSemantic | None,
        unresolved_columns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "database_name": database.display_name or database.name,
            "schema_name": table.schema.name,
            "table_name": table.name,
            "table_description": table.description or "",
            "column_data_type": "",
            "business_domain": semantic.business_domain if semantic else "",
            "semantic_summary": semantic.business_summary if semantic else "",
            "analysis_notes": semantic.analysis_notes if semantic else "",
            "existing_business_glossary": semantic.business_glossary if semantic else [],
            "table_columns": [
                {"name": column.name, "data_type": column.data_type, "description": column.description or ""}
                for column in table.columns or []
            ],
            "unresolved_columns": unresolved_columns,
            "column_name": "",
            "column_description": "",
        }

    async def _fetch_database_semantic(self, database_id: int) -> DatabaseSemantic | None:
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == database_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_table_with_column(self, column_id: int) -> tuple[DatabaseColumn, DatabaseTable, ConnectedDatabase]:
        result = await self.db.execute(
            select(DatabaseColumn)
            .options(
                selectinload(DatabaseColumn.table)
                .selectinload(DatabaseTable.schema)
                .selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseColumn.table).selectinload(DatabaseTable.columns),
            )
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
        stage_start = time.monotonic()
        column, table, database = await self._fetch_table_with_column(column_id)
        existing = await self.get_by_column_id(column_id)
        if existing and not self._needs_classification(column, table, existing, force):
            return existing

        semantic = await self._fetch_database_semantic(database.id)
        fingerprint = self._column_metadata_fingerprint(column, table)
        rulebook = self._governance_rulebook()
        compiled_rules = self._compile_rule_patterns(rulebook)
        rule_hit = self._rule_engine_match(column.name, column.description, compiled_rules=compiled_rules)
        if rule_hit[0] and not force:
            classification = PIIClassificationResult(
                is_pii=True,
                pii_type=rule_hit[1],
                risk_level=rule_hit[2],
                confidence_score=rule_hit[3],
                classification_source="rule",
                review_status="auto_approved",
                prompt_id="pii_classification",
                prompt_version="1.0",
                model_name="rules_engine",
                classified_at=datetime.now(timezone.utc),
                metadata_fingerprint=fingerprint,
                notes="Rule engine matched obvious PII pattern.",
            )
            row = await self._upsert_semantic(column, database.id, classification, ai_result=None)
            _log_stage_duration("pii classification / rules", stage_start, column_id=column_id, database_id=database.id)
            return row

        prompt_context = self._classification_context(column, table, database, semantic)
        prompt_cfg = self._governance_config()
        decision_rules = prompt_cfg.get("decision_rules", {})
        prompt_id = decision_rules.get("default_prompt_id", "pii_classification")
        model_name = settings.azure_openai_deployment or decision_rules.get("fallback_model_name", "azure_openai")
        prompt_context["governance_rulebook"] = rulebook
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
                "table_id": table.id,
                "column_id": column.id,
            },
        )
        _log_stage_duration(
            "pii classification / azure openai",
            stage_start,
            column_id=column_id,
            database_id=database.id,
            prompt_id=prompt.metadata.id,
        )

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
        ai_result: Any | None,
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

    async def _classify_table(self, table: DatabaseTable, database: ConnectedDatabase, force: bool = False) -> list[ColumnSemantic]:
        semantic = await self._fetch_database_semantic(database.id)
        existing_rows = {row.column_id: row for row in await self.get_by_database_id(database.id)}
        unresolved: list[DatabaseColumn] = []
        results: list[ColumnSemantic] = []
        rulebook = self._governance_rulebook()
        compiled_rules = self._compile_rule_patterns(rulebook)
        for column in table.columns or []:
            existing = existing_rows.get(column.id)
            fingerprint = self._column_metadata_fingerprint(column, table)
            rule_hit = self._rule_engine_match(column.name, column.description, compiled_rules=compiled_rules)
            if rule_hit[0] and not force:
                classification = PIIClassificationResult(
                    is_pii=True,
                    pii_type=rule_hit[1],
                    risk_level=rule_hit[2],
                    confidence_score=rule_hit[3],
                    classification_source="rule",
                    review_status="auto_approved",
                    prompt_id="pii_classification",
                    prompt_version="1.0",
                    model_name="rules_engine",
                    classified_at=datetime.now(timezone.utc),
                    metadata_fingerprint=fingerprint,
                    notes="Rule engine matched obvious PII pattern.",
                )
                results.append(await self._upsert_semantic(column, database.id, classification, None))
                continue
            if existing and not force and existing.metadata_fingerprint == fingerprint:
                results.append(existing)
                continue
            unresolved.append(column)

        if not unresolved:
            return results

        prompt_context = self._table_classification_context(
            table,
            database,
            semantic,
            [
                {"column_id": column.id, "column_name": column.name, "data_type": column.data_type, "description": column.description or ""}
                for column in unresolved
            ],
        )
        prompt_cfg = self._governance_config()
        decision_rules = prompt_cfg.get("decision_rules", {})
        prompt_id = decision_rules.get("default_prompt_id", "pii_classification")
        model_name = settings.azure_openai_deployment or decision_rules.get("fallback_model_name", "azure_openai")
        prompt_context["governance_rulebook"] = rulebook
        prompt = self.registry.render_prompt(prompt_id, prompt_context, category="semantic")
        observability = AIObservabilityService()
        result = await observability.generate(
            operation="chat",
            module="pii_governance",
            artifact_type="table_pii_classification",
            database_id=database.id,
            database_name=database.display_name or database.name,
            prompt_id=prompt.metadata.id,
            prompt_version=prompt.metadata.version,
            model_name=model_name,
            messages=[
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_prompt},
            ],
            request_kwargs={"response_format": {"type": "json_object"}, "max_completion_tokens": 1200},
            completeness_score=1.0,
            coverage_score=1.0 if semantic else 0.5,
            confidence_score=0.0,
            extra_metadata={"table_id": table.id, "database_id": database.id, "trigger_source": "table_governance"},
        )
        payload = {}
        try:
            payload = json.loads((result.content or "").strip() or "{}")
        except Exception:
            logger.warning("Table-level PII classification returned invalid JSON for table_id=%s", table.id)
        resolved = payload.get("resolved_columns", []) if isinstance(payload, dict) else []
        resolved_map = {item.get("column_name"): item for item in resolved if isinstance(item, dict)}
        for column in unresolved:
            item = resolved_map.get(column.name)
            if item:
                classification = PIIClassificationResult(
                    is_pii=bool(item.get("is_pii")),
                    pii_type=item.get("pii_type"),
                    risk_level=item.get("risk_level"),
                    confidence_score=float(item.get("confidence_score", 0.0)),
                    classification_source=str(item.get("classification_source", "llm")),
                    review_status=str(item.get("review_status", "needs_review")),
                    prompt_id=prompt.metadata.id,
                    prompt_version=str(prompt.metadata.version),
                    model_name=model_name,
                    classified_at=datetime.now(timezone.utc),
                    metadata_fingerprint=self._column_metadata_fingerprint(column, table),
                    notes=str(item.get("notes")) if item.get("notes") else None,
                )
                results.append(await self._upsert_semantic(column, database.id, classification, result))
            else:
                results.append(await self.classify_column(column.id, force=force))
        return results

    async def generate_for_database(self, database_id: int, force: bool = False) -> list[ColumnSemantic]:
        """Governance engine: rule-first, table-batched AI, then targeted column fallback."""
        stage_start = time.monotonic()
        database = await self._fetch_database(database_id)
        semantic = await self._fetch_database_semantic(database_id)
        if semantic is None or semantic.generation_status != SemanticGenerationStatus.completed:
            logger.info(
                "PII generation running without completed semantic intelligence for database %s",
                database_id,
            )

        columns = await self._get_columns_for_database(database_id)
        current_ids = {column.id for column in columns}
        await self._cleanup_orphans(database_id, current_ids)

        table_map: dict[int, list[DatabaseColumn]] = {}
        table_by_id: dict[int, DatabaseTable] = {}
        for column in columns:
            table = column.table
            if table is None:
                continue
            table_by_id[table.id] = table
            table_map.setdefault(table.id, []).append(column)

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
            for table_id, table_columns in table_map.items():
                try:
                    table = table_by_id[table_id]
                    table_results = await self._classify_table(table, database, force=force)
                    results.extend(table_results)
                except Exception as exc:
                    logger.exception("PII classification failed for table_id=%s: %s", table_id, exc)
            _log_stage_duration("pii classification / batch", stage_start, database_id=database_id, columns=column_count)
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
            .options(
                selectinload(DatabaseColumn.table)
                .selectinload(DatabaseTable.schema)
                .selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseColumn.table).selectinload(DatabaseTable.columns),
            )
            .join(DatabaseTable)
            .join(DatabaseSchema)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().all())
