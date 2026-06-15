"""Metadata-driven column governance: AI classification and governance packages."""

from __future__ import annotations

import hashlib
import json
import logging
import enum
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.config.manager import get_config_manager
from app.models.column_semantic import ColumnSemantic
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    GovernancePackage,
    SemanticGenerationStatus,
)
from app.config.package_registry import package_is_enabled
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
    business_meaning: str | None = None
    governance_reasoning: str | None = None
    table_purpose: str | None = None
    notes: str | None = None
    execution_status: str = "success"


class ExecutionContext(str, enum.Enum):
    ADMIN = "ADMIN"
    PIPELINE = "PIPELINE"
    MANUAL = "MANUAL"
    DEBUG = "DEBUG"
    SYSTEM = "SYSTEM"


class ColumnSemanticService:
    """Metadata-driven governance backed by column_semantics storage."""

    PROMPT_ID = "pii_classification"
    MAX_COLUMNS_PER_BATCH = 12

    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = get_prompt_registry()

    @staticmethod
    def _trace_id_as_string(trace_id: Any) -> str | None:
        if trace_id is None:
            return None
        return str(trace_id)

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

    @staticmethod
    def _stage_metadata_fingerprint(*parts: Any) -> str:
        digest = hashlib.sha256(json.dumps(parts, default=str, sort_keys=True).encode("utf-8")).hexdigest()
        return digest[:32]

    def _metadata_package(
        self,
        table: DatabaseTable,
        database: ConnectedDatabase,
        semantic: DatabaseSemantic | None,
        columns: list[DatabaseColumn] | None = None,
    ) -> dict[str, Any]:
        selected_columns = columns if columns is not None else list(table.columns or [])
        payload: dict[str, Any] = {
            "database_name": database.display_name or database.name,
            "schema_name": table.schema.name,
            "table_name": table.name,
            "table_description": table.description or "",
            "columns": [
                {
                    "name": column.name,
                    "data_type": column.data_type,
                    "nullable": bool(column.is_nullable),
                    "primary_key": bool(column.is_primary_key),
                    "foreign_key": bool(column.is_foreign_key),
                }
                for column in sorted(selected_columns, key=lambda item: item.ordinal_position or 0)
            ],
        }
        return payload

    @staticmethod
    def _column_batches(columns: list[DatabaseColumn], batch_size: int) -> list[list[DatabaseColumn]]:
        if batch_size <= 0:
            return [columns]
        return [columns[idx : idx + batch_size] for idx in range(0, len(columns), batch_size)]

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

    async def classify_column(
        self,
        column_id: int,
        force: bool = False,
        *,
        execution_context: ExecutionContext,
    ) -> ColumnSemantic:
        if not package_is_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")
        if execution_context not in {ExecutionContext.ADMIN, ExecutionContext.MANUAL, ExecutionContext.DEBUG}:
            raise ValueError(
                "Automated flows must use table-level governance; classify_column() only accepts ADMIN, MANUAL, or DEBUG execution contexts."
            )
        column, table, database = await self._fetch_table_with_column(column_id)
        table_results = await self._classify_table(table, database, force=force)
        for row in table_results:
            if row.column_id == column.id:
                return row
        raise ValueError(f"Column {column_id} was not classified")

    def _classification_from_column_payload(
        self,
        item: dict[str, Any],
        *,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        metadata_fingerprint: str,
        table_purpose: str | None,
        source: str = "table_ai",
    ) -> PIIClassificationResult:
        is_pii = bool(item.get("is_pii"))
        confidence = float(item.get("confidence_score", 0.0))
        pii_type = item.get("pii_type")
        if not is_pii or pii_type in (None, "", "null"):
            pii_type = None
        risk_level = item.get("risk_level") or (self._risk_from_probability(confidence) if is_pii else "low")
        return PIIClassificationResult(
            is_pii=is_pii,
            pii_type=pii_type,
            risk_level=risk_level if is_pii else "low",
            confidence_score=max(0.0, min(1.0, confidence)),
            classification_source=str(item.get("classification_source", source)),
            review_status=str(item.get("review_status", self._review_status_from_confidence(confidence))),
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=model_name,
            classified_at=datetime.now(timezone.utc),
            metadata_fingerprint=metadata_fingerprint,
            business_meaning=item.get("business_meaning"),
            governance_reasoning=item.get("governance_reasoning"),
            table_purpose=table_purpose,
            notes=item.get("notes"),
        )

    @staticmethod
    def _overall_risk_from_columns(columns: list[dict[str, Any]]) -> str | None:
        risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        highest = 0
        highest_label: str | None = None
        for item in columns:
            level = str(item.get("risk_level") or "").lower()
            if level in risk_order and risk_order[level] > highest:
                highest = risk_order[level]
                highest_label = level
        return highest_label

    @staticmethod
    def _governance_error_message(exc: BaseException) -> str:
        message = str(exc).strip()
        if message.startswith("azure_empty_response"):
            return "azure_empty_response"
        if message.startswith("missing_required_sections:"):
            return message.replace("missing_required_sections:", "missing_required_fields:", 1)
        return message or "governance_failed"

    async def _upsert_failed_semantic(
        self,
        column: DatabaseColumn,
        database_id: int,
        *,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        metadata_fingerprint: str,
        error_message: str,
        ai_result: Any | None,
    ) -> ColumnSemantic:
        row = await self.get_by_column_id(column.id)
        if row is None:
            row = ColumnSemantic(column_id=column.id, database_id=database_id)
            self.db.add(row)
        row.business_name = column.name.replace("_", " ").title()
        row.business_description = column.description or ""
        row.business_meaning = None
        row.governance_reasoning = None
        row.table_purpose = None
        row.column_category = None
        row.table_category = column.table.table_type.value if getattr(column, "table", None) else None
        row.pii_type = None
        row.risk_level = None
        row.classification_source = "table_ai"
        row.prompt_id = prompt_id
        row.prompt_version = prompt_version
        row.model_name = model_name
        row.execution_status = "failed"
        row.used_fallback = False
        row.error_message = error_message
        row.trace_id = self._trace_id_as_string(getattr(ai_result, "trace_id", None) if ai_result is not None else None)
        row.metadata_fingerprint = metadata_fingerprint
        row.generated_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return row

    async def _persist_table_failure(
        self,
        columns: list[DatabaseColumn],
        database_id: int,
        *,
        table: DatabaseTable,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        error_message: str,
        ai_result: Any | None,
    ) -> list[ColumnSemantic]:
        results: list[ColumnSemantic] = []
        for column in columns:
            results.append(
                await self._upsert_failed_semantic(
                    column,
                    database_id,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    model_name=model_name,
                    metadata_fingerprint=self._column_metadata_fingerprint(column, table),
                    error_message=error_message,
                    ai_result=ai_result,
                )
            )
        return results

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
        row.business_meaning = classification.business_meaning
        row.governance_reasoning = classification.governance_reasoning
        row.table_purpose = classification.table_purpose
        row.column_category = "pii" if classification.is_pii else "non_pii"
        row.table_category = column.table.table_type.value if getattr(column, "table", None) else None
        row.is_pii = classification.is_pii
        row.pii_type = classification.pii_type
        row.risk_level = classification.risk_level
        row.confidence_score = classification.confidence_score
        row.prompt_id = classification.prompt_id
        row.prompt_version = classification.prompt_version
        row.model_name = classification.model_name
        row.classification_source = classification.classification_source
        row.execution_status = classification.execution_status
        row.used_fallback = False
        row.error_message = None
        row.trace_id = self._trace_id_as_string(getattr(ai_result, "trace_id", None) if ai_result is not None else None)
        row.metadata_fingerprint = classification.metadata_fingerprint
        row.generated_at = classification.classified_at
        row.updated_at = classification.classified_at
        await self.db.flush()
        return row

    async def _classify_table(
        self,
        table: DatabaseTable,
        database: ConnectedDatabase,
        force: bool = False,
    ) -> list[ColumnSemantic]:
        if not package_is_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")

        columns = sorted(table.columns or [], key=lambda item: item.ordinal_position or 0)
        if not columns:
            return []

        semantic = await self._fetch_database_semantic(database.id)
        existing_rows = {row.column_id: row for row in await self.get_by_database_id(database.id)}
        if not force and all(
            existing_rows.get(column.id)
            and existing_rows[column.id].metadata_fingerprint == self._column_metadata_fingerprint(column, table)
            for column in columns
        ):
            return [existing_rows[column.id] for column in columns if existing_rows.get(column.id)]

        results: list[ColumnSemantic] = []
        model_name = settings.azure_openai_deployment or "azure_openai"
        max_completion_tokens = int(get_config_manager().get_model_config("schema_enrichment").get("max_completion_tokens", 1000) or 1000)
        observability = AIObservabilityService()
        for batch_index, batch in enumerate(self._column_batches(columns, self.MAX_COLUMNS_PER_BATCH), start=1):
            prompt_context = self._metadata_package(table, database, semantic, columns=batch)
            prompt_context_size = len(json.dumps(prompt_context, default=str))
            prompt = self.registry.render_prompt(self.PROMPT_ID, prompt_context, category="semantic")
            prompt_size = len(prompt.system_message or "") + len(prompt.user_prompt or "")
            logger.info(
                "Governance prompt prepared | table_id=%s batch=%s columns=%s prompt_chars=%s context_chars=%s",
                table.id,
                batch_index,
                len(batch),
                prompt_size,
                prompt_context_size,
            )
            ai_result: Any | None = None
            try:
                ai_result = await observability.generate(
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
                    request_kwargs={
                        "response_format": {"type": "json_object"},
                        "max_completion_tokens": max_completion_tokens,
                        "reasoning_effort": "low",
                        "_retry_on_length": 1,
                    },
                    completeness_score=1.0,
                    coverage_score=1.0 if semantic else 0.5,
                    confidence_score=0.0,
                    execution_status="success",
                    fallback_used=False,
                    retry_count=0,
                    extra_metadata={
                        "table_id": table.id,
                        "database_id": database.id,
                        "stage": "governance",
                        "classification_source": "table_ai",
                        "column_count": len(batch),
                        "batch_index": batch_index,
                        "batch_count": (len(columns) + self.MAX_COLUMNS_PER_BATCH - 1) // self.MAX_COLUMNS_PER_BATCH,
                        "metadata_fingerprint": self._stage_metadata_fingerprint(database.id, table.id, [c.id for c in batch]),
                    },
                )
                usage = getattr(ai_result, "token_usage", {}) or {}
                raw_response = getattr(ai_result, "raw_response", None)
                finish_reason = None
                try:
                    if raw_response and getattr(raw_response, "choices", None):
                        finish_reason = getattr(raw_response.choices[0], "finish_reason", None)
                except Exception:
                    finish_reason = None
                logger.info(
                    "Governance AI result | table_id=%s batch=%s finish_reason=%s prompt_tokens=%s completion_tokens=%s reasoning_tokens=%s content_chars=%s",
                    table.id,
                    batch_index,
                    finish_reason,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("reasoning_tokens"),
                    len(ai_result.content or ""),
                )
                payload = self._parse_table_classification(ai_result.content or "")
                logger.info("Governance response received | table_id=%s batch=%s content_chars=%s", table.id, batch_index, len(ai_result.content or ""))
            except ValueError as exc:
                error_message = self._governance_error_message(exc)
                usage = getattr(ai_result, "token_usage", {}) if ai_result is not None else {}
                usage = usage or {}
                raw_response = getattr(ai_result, "raw_response", None) if ai_result is not None else None
                finish_reason = None
                try:
                    if raw_response and getattr(raw_response, "choices", None):
                        finish_reason = getattr(raw_response.choices[0], "finish_reason", None)
                except Exception:
                    finish_reason = None
                logger.warning(
                    "Table-level governance classification failed for table_id=%s batch=%s: %s finish_reason=%s prompt_tokens=%s completion_tokens=%s reasoning_tokens=%s",
                    table.id,
                    batch_index,
                    error_message,
                    finish_reason,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("reasoning_tokens"),
                )
                failures = await self._persist_table_failure(
                    batch,
                    database.id,
                    table=table,
                    prompt_id=prompt.metadata.id,
                    prompt_version=str(prompt.metadata.version),
                    model_name=model_name,
                    error_message=error_message,
                    ai_result=ai_result,
                )
                await self._persist_governance_package_failure(
                    table,
                    database,
                    prompt_id=prompt.metadata.id,
                    prompt_version=str(prompt.metadata.version),
                    model_name=model_name,
                    error_message=error_message,
                    ai_result=ai_result,
                )
                return failures

            table_purpose = payload.get("business_purpose") or payload.get("table_summary")
            resolved = payload.get("resolved_columns", [])
            resolved_map = {
                str(item.get("column_name")): item
                for item in resolved
                if isinstance(item, dict) and item.get("column_name")
            }

            for column in batch:
                item = resolved_map.get(column.name)
                fingerprint = self._column_metadata_fingerprint(column, table)
                if not item:
                    results.append(
                        await self._upsert_failed_semantic(
                            column,
                            database.id,
                            prompt_id=prompt.metadata.id,
                            prompt_version=str(prompt.metadata.version),
                            model_name=model_name,
                            metadata_fingerprint=fingerprint,
                            error_message=f"missing_required_fields:column_result:{column.name}",
                            ai_result=ai_result,
                        )
                    )
                    continue
                classification = self._classification_from_column_payload(
                    item,
                    prompt_id=prompt.metadata.id,
                    prompt_version=str(prompt.metadata.version),
                    model_name=model_name,
                    metadata_fingerprint=fingerprint,
                    table_purpose=table_purpose,
                )
                results.append(await self._upsert_semantic(column, database.id, classification, ai_result))
            await self._upsert_governance_package(
                table,
                database,
                prompt_id=prompt.metadata.id,
                prompt_version=str(prompt.metadata.version),
                model_name=model_name,
                payload=payload,
                ai_result=ai_result,
            )
        return results

    async def _upsert_governance_package(
        self,
        table: DatabaseTable,
        database: ConnectedDatabase,
        *,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        payload: dict[str, Any],
        ai_result: Any | None,
        error_message: str | None = None,
    ) -> GovernancePackage:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.table_id == table.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = GovernancePackage(table_id=table.id, database_id=database.id)
            self.db.add(row)
        resolved = list(payload.get("resolved_columns") or [])
        pii_columns = [item for item in resolved if item.get("is_pii")]
        risk_columns = [item for item in resolved if str(item.get("risk_level") or "").lower() in {"high", "critical"}]
        sensitive_columns = [item for item in resolved if item.get("is_pii") or str(item.get("risk_level") or "").lower() in {"high", "critical"}]
        row.table_name = table.name
        row.schema_name = table.schema.name
        row.table_summary = payload.get("table_summary") or ""
        row.business_purpose = payload.get("business_purpose") or ""
        row.pii_columns = pii_columns
        row.risk_columns = risk_columns
        row.sensitive_columns = sensitive_columns
        row.overall_risk = self._overall_risk_from_columns(resolved)
        row.confidence_score = max(
            0.0,
            min(1.0, float(sum(float(item.get("confidence_score", 0.0) or 0.0) for item in resolved) / max(1, len(resolved)) if resolved else 0.0)),
        )
        row.prompt_id = prompt_id
        row.prompt_version = prompt_version
        row.model_name = model_name
        row.trace_id = str(getattr(ai_result, "trace_id", None)) if ai_result is not None else None
        row.raw_failure_reason = error_message
        row.updated_at = datetime.now(timezone.utc)
        if row.id is None:
            row.created_at = datetime.now(timezone.utc)
        await self.db.flush()
        return row

    async def _persist_governance_package_failure(
        self,
        table: DatabaseTable,
        database: ConnectedDatabase,
        *,
        prompt_id: str,
        prompt_version: str,
        model_name: str,
        error_message: str,
        ai_result: Any | None,
    ) -> GovernancePackage:
        return await self._upsert_governance_package(
            table,
            database,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model_name=model_name,
            payload={"resolved_columns": [], "table_summary": "", "business_purpose": ""},
            ai_result=ai_result,
            error_message=error_message,
        )

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
            "confidence_score": float(row.confidence_score or 0.0),
            "prompt_id": row.prompt_id,
            "prompt_version": row.prompt_version,
            "model_name": row.model_name,
            "trace_id": row.trace_id,
            "raw_failure_reason": row.raw_failure_reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _parse_table_classification(response_text: str) -> dict[str, Any]:
        cleaned = (response_text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if not cleaned:
            raise ValueError("empty_ai_response")
        try:
            payload = json.loads(cleaned)
        except Exception as exc:
            raise ValueError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_json")
        if "resolved_columns" not in payload or not isinstance(payload.get("resolved_columns"), list):
            raise ValueError("missing_required_sections:resolved_columns")
        return payload

    async def generate_for_database(self, database_id: int, force: bool = False) -> list[ColumnSemantic]:
        """Governance engine: one metadata-driven AI request per table."""
        stage_start = time.monotonic()
        if not package_is_enabled("governance"):
            raise ValueError("Governance package is disabled by registry")
        database = await self._fetch_database(database_id)
        semantic = await self._fetch_database_semantic(database_id)
        if semantic is None or semantic.generation_status != SemanticGenerationStatus.completed:
            logger.info(
                "Governance running without completed semantic intelligence for database %s",
                database_id,
            )

        columns = await self._get_columns_for_database(database_id)
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
            prompt_id=self.PROMPT_ID,
            prompt_version="2.0",
            database_id=database.id,
            database_name=database.display_name or database.name,
            model_name=settings.azure_openai_deployment or "azure_openai",
            completeness_score=1.0 if column_count > 0 else 0.0,
            coverage_score=min(1.0, column_count / 100.0) if column_count > 0 else 0.0,
            confidence_score=0.5 if column_count > 0 else 0.0,
            execution_status="success",
            fallback_used=False,
            retry_count=0,
            extra_metadata={
                "column_count": column_count,
                "readiness_category": "governance",
                "force": force,
                "database_id": database.id,
                "stage": "governance",
                "metadata_fingerprint": self._stage_metadata_fingerprint(database.id, column_count, force),
            },
        ):
            results: list[ColumnSemantic] = []
            for table_id in table_map:
                try:
                    table = table_by_id[table_id]
                    table_results = await self._classify_table(table, database, force=force)
                    results.extend(table_results)
                except Exception as exc:
                    logger.exception("Governance classification failed for table_id=%s: %s", table_id, exc)
            _log_stage_duration("governance classification / batch", stage_start, database_id=database_id, columns=column_count)
            return results

    async def governance_summary(self, database_id: int) -> dict[str, Any]:
        """Aggregate governance intelligence for downstream prompt and readiness consumers."""
        rows = await self.get_by_database_id(database_id)
        total_columns = await self._count_columns(database_id)
        successful_rows = [row for row in rows if row.execution_status == "success"]
        pii_columns = [row for row in successful_rows if row.is_pii]
        risk_columns = [
            row
            for row in successful_rows
            if row.risk_level and row.risk_level.lower() in {"high", "critical"}
        ]
        classified = [row for row in successful_rows if row.pii_type or not row.is_pii]
        governance_complete = (
            bool(successful_rows)
            and len(successful_rows) >= total_columns
            and total_columns > 0
            and not any(row.execution_status == "failed" for row in rows)
        )
        return {
            "column_semantics": len(successful_rows),
            "total_columns": total_columns,
            "pii_columns": len(pii_columns),
            "pii_typed_columns": len([row for row in pii_columns if row.pii_type]),
            "pii_risk_tagged_columns": len([row for row in pii_columns if row.risk_level]),
            "risk_columns": len(risk_columns),
            "pii_identified_coverage": round((len(successful_rows) / max(1, total_columns)) * 100.0, 2),
            "pii_classified_coverage": round((len(classified) / max(1, len(successful_rows))) * 100.0, 2) if successful_rows else 0.0,
            "prompt_protection_enabled": bool(settings.pii_prompt_protection_enabled and governance_complete),
            "embedding_protection_enabled": bool(settings.pii_embedding_protection_enabled and governance_complete),
            "governance_complete": governance_complete,
        }

    async def build_governance_package(self, database_id: int) -> dict[str, Any]:
        """Build persisted governance packages grouped by table."""
        result = await self.db.execute(
            select(GovernancePackage)
            .where(GovernancePackage.database_id == database_id)
            .order_by(GovernancePackage.schema_name, GovernancePackage.table_name)
        )
        packages = [self._governance_package_to_dict(row) for row in result.scalars().all()]
        return {
            "database_id": database_id,
            "table_count": len(packages),
            "packages": packages,
        }

    async def get_governance_package(self, table_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.table_id == table_id)
        )
        row = result.scalar_one_or_none()
        return self._governance_package_to_dict(row) if row else None

    async def get_governance_pii_summary(self, database_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(GovernancePackage).where(GovernancePackage.database_id == database_id)
        )
        packages = result.scalars().all()
        return {
            "database_id": database_id,
            "table_count": len(packages),
            "pii_columns": sum(len(pkg.pii_columns) for pkg in packages),
            "risk_columns": sum(len(pkg.risk_columns) for pkg in packages),
            "sensitive_columns": sum(len(pkg.sensitive_columns) for pkg in packages),
            "governance_packages": len(packages),
        }

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
