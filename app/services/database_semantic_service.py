"""
DatabaseSemanticService — Database-level semantic enrichment using Azure OpenAI.

Converts database metadata into AI-understandable business context:
- Business domain
- Business summary
- Key entities
- Business glossary
- Suggested use cases
- Confidence score
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.config.prompts import get_semantic_prompt
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    SemanticGenerationStatus,
)
from app.schema_engine.embeddings import _traceable
from app.services.ai_observability_service import AIObservabilityService, AIObservationResult
from app.utils import safe_flush

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_ENTITIES_TO_SAMPLE = 50
MAX_RELATIONSHIPS_TO_SAMPLE = 100
MAX_TABLES_IN_PROMPT = 20
MAX_COLUMNS_PER_TABLE_IN_PROMPT = 8
MAX_RELATIONSHIPS_IN_PROMPT = 40
CONFIDENCE_POOR_NAMING_PENALTY = 0.15
CONFIDENCE_INCOMPLETE_RELATIONSHIPS_PENALTY = 0.10


# ── Database Semantic Enrichment Data Model ──────────────────────────────────

class DatabaseSemanticEnrichment:
    """Container for database-level enriched semantic data."""

    def __init__(
        self,
        source_id: int,
        business_domain: str,
        business_summary: str,
        key_entities: list[str],
        business_glossary: list[dict],
        suggested_use_cases: list[str],
        confidence_score: float,
        analysis_notes: Optional[str] = None,
        raw_response: Optional[str] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.source_id = source_id
        self.business_domain = business_domain
        self.business_summary = business_summary
        self.analysis_notes = analysis_notes
        self.key_entities = key_entities
        self.business_glossary = business_glossary
        self.suggested_use_cases = suggested_use_cases
        self.confidence_score = confidence_score
        self.raw_response = raw_response
        self.generated_at = datetime.now(timezone.utc)


# ── DatabaseSemanticService ──────────────────────────────────────────────────

class DatabaseSemanticService:
    """
    Enriches database metadata with semantic business context using Azure OpenAI.
    
    Usage:
        service = DatabaseSemanticService(db_session)
        enrichment = await service.generate_database_semantics(source_id)
        await service.save_enrichment(enrichment)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _apply_enrichment_fields(
        self,
        db_semantic: DatabaseSemantic,
        enrichment: DatabaseSemanticEnrichment,
        status: SemanticGenerationStatus,
    ) -> None:
        """Copy generated semantic values onto an ORM row."""
        db_semantic.business_domain = enrichment.business_domain
        db_semantic.business_summary = enrichment.business_summary
        db_semantic.analysis_notes = enrichment.analysis_notes
        db_semantic.key_entities = enrichment.key_entities
        db_semantic.business_glossary = enrichment.business_glossary
        db_semantic.suggested_use_cases = enrichment.suggested_use_cases
        db_semantic.confidence_score = enrichment.confidence_score
        db_semantic.raw_ai_response = enrichment.raw_response
        db_semantic.error_message = None
        db_semantic.generation_status = status
        db_semantic.generated_at = enrichment.generated_at
        db_semantic.updated_at = datetime.now(timezone.utc)

    def _apply_profile_clear_fields(
        self,
        db_semantic: DatabaseSemantic,
        status: SemanticGenerationStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Clear stale semantic content when a generation attempt does not succeed."""
        now = datetime.now(timezone.utc)
        db_semantic.business_domain = None
        db_semantic.business_summary = None
        db_semantic.analysis_notes = None
        db_semantic.key_entities = []
        db_semantic.business_glossary = []
        db_semantic.suggested_use_cases = []
        db_semantic.confidence_score = 0.0
        db_semantic.raw_ai_response = None
        db_semantic.error_message = error_message
        db_semantic.generation_status = status
        db_semantic.generated_at = now
        db_semantic.updated_at = now

    def _apply_status_fields(
        self,
        db_semantic: DatabaseSemantic,
        status: SemanticGenerationStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a semantic row with a non-success status."""
        db_semantic.generation_status = status
        db_semantic.error_message = error_message
        db_semantic.updated_at = datetime.now(timezone.utc)

    async def get_or_create_semantic(
        self,
        source_id: int,
        enrichment: Optional[DatabaseSemanticEnrichment] = None,
        status: SemanticGenerationStatus = SemanticGenerationStatus.completed,
        error_message: Optional[str] = None,
    ) -> tuple[DatabaseSemantic, bool]:
        """
        Fetch the semantic row for a database or create it safely.

        This method is idempotent and tolerates concurrent create requests.
        """
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == source_id)
        )
        db_semantic = result.scalars().first()
        created = db_semantic is None

        if db_semantic is None:
            db_semantic = DatabaseSemantic(source_id=source_id)
            self.db.add(db_semantic)

        if enrichment is not None:
            self._apply_enrichment_fields(db_semantic, enrichment, status)
        elif error_message is not None:
            self._apply_profile_clear_fields(db_semantic, status=status, error_message=error_message)
        else:
            self._apply_status_fields(db_semantic, status)

        try:
            await safe_flush(self.db)
        except IntegrityError:
            # Another request inserted the row first. Reload and update it in place.
            await self.db.rollback()
            result = await self.db.execute(
                select(DatabaseSemantic).where(DatabaseSemantic.source_id == source_id)
            )
            db_semantic = result.scalars().first()
            if db_semantic is None:
                raise
            created = False

            if enrichment is not None:
                self._apply_enrichment_fields(db_semantic, enrichment, status)
            elif error_message is not None:
                self._apply_profile_clear_fields(db_semantic, status=status, error_message=error_message)
            else:
                self._apply_status_fields(db_semantic, status)

            await safe_flush(self.db)

        await self.db.refresh(db_semantic)
        return db_semantic, created

    # ── Main semantic generation method ────────────────────────────────────

    @_traceable("generate_database_semantics", run_type="chain")
    async def generate_database_semantics(self, source_id: int) -> DatabaseSemanticEnrichment:
        """
        Generate semantic context for an entire database.
        
        Args:
            source_id: Primary key of the connected database
            
        Returns:
            DatabaseSemanticEnrichment object with business context
            
        Raises:
            ValueError: If database not found or no metadata available
        """
        start_time = time.time()

        # Fetch database with all metadata
        database = await self._fetch_database_with_metadata(source_id)
        if not database:
            raise ValueError(f"Database {source_id} not found")

        # Check if database has metadata
        if not database.schemas or len(database.schemas) == 0:
            logger.warning("Database %d has no schemas", source_id)
            raise ValueError("no_metadata")

        # Build metadata summary
        metadata_payload = await self._build_metadata_summary(database)
        
        # Validate payload size
        if not self._validate_payload_size(metadata_payload):
            logger.warning("Database %d has very large schema - sampling entities", source_id)
            metadata_payload = self._sample_large_schema(metadata_payload)

        logger.info("Generating semantics for database %d", source_id)

        # Call Azure OpenAI
        try:
            ai_result = await self._call_azure_openai(database, metadata_payload)
        except Exception as e:
            logger.error("Azure OpenAI call failed for database %d: %s", source_id, e, exc_info=True)
            raise

        # Parse response
        response_text = ai_result.content or ""
        enrichment = self._parse_enrichment_response(source_id, response_text, metadata_payload)

        # Calculate confidence score
        confidence = self._calculate_confidence_score(database, enrichment)
        enrichment.confidence_score = confidence

        logger.info(
            "Completed semantic generation for database %d with confidence %.2f",
            source_id,
            confidence,
        )

        return enrichment

    @_traceable("generate_and_store_semantics", run_type="chain")
    async def generate_and_store_semantics(self, source_id: int) -> tuple[DatabaseSemantic, float]:
        """
        Generate database semantics and persist the latest profile.

        This is the end-to-end workflow used by the API:
        load metadata -> build summary -> call OpenAI -> parse -> store -> return.
        """
        start_time = time.time()

        database = await self._fetch_database_with_metadata(source_id)
        if not database:
            raise ValueError(f"Database {source_id} not found")

        semantic_row, _ = await self.get_or_create_semantic(
            source_id,
            status=SemanticGenerationStatus.processing,
        )

        try:
            if not database.schemas or len(database.schemas) == 0:
                logger.warning("Database %d has no schemas", source_id)
                semantic_row, _ = await self.get_or_create_semantic(
                    source_id,
                    status=SemanticGenerationStatus.no_metadata,
                    error_message="No metadata available in database",
                )
                return semantic_row, (time.time() - start_time) * 1000

            metadata_payload = await self._build_metadata_summary(database)
            if not self._validate_payload_size(metadata_payload):
                logger.warning("Database %d has very large schema - sampling entities", source_id)
                metadata_payload = self._sample_large_schema(metadata_payload)

            logger.info("Generating semantics for database %d", source_id)
            ai_result = await self._call_azure_openai(database, metadata_payload)
            response_text = ai_result.content or ""
            enrichment = self._parse_enrichment_response(source_id, response_text, metadata_payload)
            enrichment.confidence_score = self._calculate_confidence_score(database, enrichment)

            semantic_row = await self.save_enrichment(enrichment, SemanticGenerationStatus.completed)
            return semantic_row, (time.time() - start_time) * 1000

        except ValueError:
            raise
        except Exception as exc:
            logger.error("Semantic generation failed for database %d: %s", source_id, exc, exc_info=True)
            semantic_row, _ = await self.get_or_create_semantic(
                source_id,
                status=SemanticGenerationStatus.failed,
                error_message=str(exc),
            )
            raise

    # ── Metadata fetching ──────────────────────────────────────────────────

    async def _fetch_database_with_metadata(self, source_id: int) -> Optional[ConnectedDatabase]:
        """Fetch database with all schemas, tables, columns, and relationships loaded."""
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == source_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(
                    DatabaseTable.columns
                ),
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.relationships_from),
            )
        )
        return result.scalars().unique().first()

    # ── Metadata summarization ─────────────────────────────────────────────

    async def _build_metadata_summary(self, database: ConnectedDatabase) -> dict[str, Any]:
        """
        Build a compact metadata summary for AI analysis.
        
        Returns structured metadata payload with:
        - Database name and type
        - Schemas and tables (including catalog descriptions when present)
        - Relationships
        - Column patterns
        """
        payload = {
            "database_name": database.name,
            "database_type": database.db_type.value,
            "schemas": [],
            "total_tables": 0,
            "total_relationships": 0,
            "naming_patterns": {},
        }

        # Collect schema information
        for schema in database.schemas or []:
            schema_info: dict[str, Any] = {
                "name": schema.name,
                "tables": [],
                "table_count": len(schema.tables) if schema.tables else 0,
            }
            schema_description = self._normalize_description(schema.description)
            if schema_description:
                schema_info["description"] = schema_description

            # Collect table information
            for table in schema.tables or []:
                table_info: dict[str, Any] = {
                    "name": table.name,
                    "type": table.table_type.value if hasattr(table.table_type, "value") else str(table.table_type),
                    "row_count": table.row_count,
                    "columns": [self._column_metadata_entry(col) for col in (table.columns or [])],
                    "relationships": [
                        {
                            "column": rel.column_name,
                            "references": f"{rel.referenced_table_name}.{rel.referenced_column_name}",
                        }
                        for rel in (table.relationships_from or [])
                    ],
                }
                table_description = self._normalize_description(table.description)
                if table_description:
                    table_info["description"] = table_description

                schema_info["tables"].append(table_info)
                payload["total_tables"] += 1
                payload["total_relationships"] += len(table.relationships_from or [])

            payload["schemas"].append(schema_info)

        # Analyze naming patterns
        payload["naming_patterns"] = self._analyze_naming_patterns(database)

        return payload

    @staticmethod
    def _normalize_description(description: Optional[str]) -> Optional[str]:
        """Return a trimmed catalog description, or None when empty."""
        if not description:
            return None
        text = description.strip()
        return text or None

    @classmethod
    def _column_metadata_entry(cls, column: DatabaseColumn) -> dict[str, Any]:
        """Build a column dict for the metadata payload."""
        entry: dict[str, Any] = {
            "name": column.name,
            "type": column.data_type,
            "is_pk": column.is_primary_key,
            "is_fk": column.is_foreign_key,
            "nullable": column.is_nullable,
        }
        column_description = cls._normalize_description(column.description)
        if column_description:
            entry["description"] = column_description
        return entry

    def _analyze_naming_patterns(self, database: ConnectedDatabase) -> dict[str, Any]:
        """Analyze naming patterns to assess metadata quality."""
        patterns = {
            "table_prefixes": set(),
            "has_poor_naming": False,
            "has_consistent_naming": True,
        }

        poor_naming_count = 0
        total_tables = 0

        for schema in database.schemas or []:
            for table in schema.tables or []:
                total_tables += 1

                # Check for poor naming (e.g., tbl_001, col_a)
                if self._is_poor_name(table.name):
                    poor_naming_count += 1

                # Extract table prefix
                parts = table.name.split("_")
                if len(parts) > 1:
                    patterns["table_prefixes"].add(parts[0])

        patterns["table_prefixes"] = list(patterns["table_prefixes"])

        if total_tables > 0:
            poor_naming_ratio = poor_naming_count / total_tables
            patterns["has_poor_naming"] = poor_naming_ratio > 0.3
            patterns["poor_naming_ratio"] = poor_naming_ratio

        return patterns

    def _is_poor_name(self, name: str) -> bool:
        """Check if a name suggests poor schema design (e.g., 'tbl_001', 'col_a')."""
        # Names that are just generic patterns
        if any(
            name.lower().startswith(prefix)
            for prefix in ["tbl_", "col_", "t_", "c_", "f_", "d_", "tmp_", "test_"]
        ):
            return True

        # Names that are just numbers or single letters after prefix
        if name.replace("_", "").isdigit():
            return True

        return False

    # ── Payload validation ─────────────────────────────────────────────────

    def _validate_payload_size(self, payload: dict[str, Any], max_size_kb: int = 512) -> bool:
        """Check if payload is within reasonable size limits."""
        payload_str = json.dumps(payload)
        size_kb = len(payload_str.encode("utf-8")) / 1024
        
        if size_kb > max_size_kb:
            logger.warning("Metadata payload is %.1f KB (max %.1f KB)", size_kb, max_size_kb)
            return False
        
        return True

    def _sample_large_schema(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Sample large schemas to reduce payload size."""
        sampled = payload.copy()
        sampled["_sampling_note"] = "Large schema - entities sampled for analysis"

        total_tables = 0
        sampled_tables = 0

        for schema in sampled.get("schemas", []):
            if len(schema.get("tables", [])) > MAX_ENTITIES_TO_SAMPLE:
                original_count = len(schema["tables"])
                schema["tables"] = schema["tables"][:MAX_ENTITIES_TO_SAMPLE]
                schema["_table_count_original"] = original_count
                sampled_tables += (original_count - MAX_ENTITIES_TO_SAMPLE)
            total_tables += len(schema.get("tables", []))

        if sampled_tables > 0:
            logger.info("Sampled schema: kept %d tables, removed %d", total_tables, sampled_tables)

        return sampled

    def _build_schema_prompt_parts(self, metadata_payload: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Build compact schema and relationship summaries from sampled metadata."""
        schema_lines: list[str] = []
        relationship_lines: list[str] = []

        for schema in (metadata_payload.get("schemas") or [])[:MAX_TABLES_IN_PROMPT]:
            schema_name = schema.get("name", "unknown")
            schema_lines.append(f"Schema: {schema_name}")
            schema_description = self._normalize_description(schema.get("description"))
            if schema_description:
                schema_lines.append(f"  Schema description: {schema_description}")

            tables = (schema.get("tables") or [])[:MAX_TABLES_IN_PROMPT]
            for table in tables:
                table_name = table.get("name", "unknown")
                table_type = table.get("type", "unknown")
                row_count = table.get("row_count", "Unknown")
                schema_lines.append(f"- Table: {table_name} | Type: {table_type} | Rows: {row_count}")
                table_description = self._normalize_description(table.get("description"))
                if table_description:
                    schema_lines.append(f"  Table description: {table_description}")

                columns = (table.get("columns") or [])[:MAX_COLUMNS_PER_TABLE_IN_PROMPT]
                if columns:
                    column_parts = [self._format_column_for_prompt(col) for col in columns]
                    schema_lines.append(f"  Columns: {', '.join(column_parts)}")

                if table.get("_table_count_original"):
                    schema_lines.append(
                        f"  Note: sampled from {table.get('_table_count_original')} tables"
                    )

                for rel in (table.get("relationships") or [])[:MAX_RELATIONSHIPS_IN_PROMPT]:
                    relationship_lines.append(
                        f"{schema_name}.{table_name}.{rel.get('column', 'unknown')} -> {rel.get('references', 'unknown')}"
                    )
                    if len(relationship_lines) >= MAX_RELATIONSHIPS_IN_PROMPT:
                        return schema_lines, relationship_lines

        return schema_lines, relationship_lines

    @classmethod
    def _format_column_for_prompt(cls, column: dict[str, Any]) -> str:
        """Format a column for the LLM schema summary, including description when present."""
        base = f"{column.get('name', 'unknown')}({column.get('type', 'unknown')})"
        description = cls._normalize_description(column.get("description"))
        if description:
            return f"{base} — {description}"
        return base

    # ── Azure OpenAI Integration ───────────────────────────────────────────

    def _build_prompt_variables(self, database: ConnectedDatabase, metadata_payload: dict[str, Any]) -> dict[str, Any]:
        """Build variables for the semantic prompt template."""
        schema_lines, relationships = self._build_schema_prompt_parts(metadata_payload)
        total_columns = 0

        for schema in database.schemas or []:
            for table in schema.tables or []:
                total_columns += len(table.columns or [])

        naming_patterns = metadata_payload.get("naming_patterns", {}) or {}
        total_tables = metadata_payload.get("total_tables", 0)
        poor_ratio = float(naming_patterns.get("poor_naming_ratio", 0) or 0)
        good_naming_rate = max(0.0, min(100.0, (1.0 - poor_ratio) * 100.0))

        return {
            "database_name": database.name,
            "database_type": database.db_type.value,
            "total_tables": total_tables,
            "total_columns": total_columns,
            "schema_summary": "\n".join(schema_lines) if schema_lines else "No schemas available.",
            "relationships_summary": "\n".join(relationships) if relationships else "No relationships found.",
            "naming_quality": round(good_naming_rate, 1),
            "poor_naming_patterns": ", ".join(naming_patterns.get("table_prefixes", [])) or "None detected",
        }

    @staticmethod
    def _semantic_completeness(metadata_payload: dict[str, Any]) -> float:
        total_tables = int(metadata_payload.get("total_tables", 0) or 0)
        total_relationships = int(metadata_payload.get("total_relationships", 0) or 0)
        if total_tables <= 0:
            return 0.0
        score = 0.5
        if total_relationships > 0:
            score += 0.25
        if metadata_payload.get("naming_patterns"):
            score += 0.25
        return round(min(1.0, score), 3)

    @staticmethod
    def _semantic_coverage(metadata_payload: dict[str, Any]) -> float:
        schemas = len(metadata_payload.get("schemas") or [])
        tables = int(metadata_payload.get("total_tables", 0) or 0)
        if tables <= 0:
            return 0.0
        coverage = min(1.0, (schemas + tables) / max(1, tables + 3))
        return round(coverage, 3)

    @_traceable("database_semantic_openai_call", run_type="llm")
    async def _call_azure_openai(self, database: ConnectedDatabase, metadata_payload: dict[str, Any]) -> AIObservationResult:
        """
        Call Azure OpenAI to generate semantic understanding.

        Returns:
            AIObservationResult with response text, token usage, and trace metadata.
        """
        prompt_variables = self._build_prompt_variables(database, metadata_payload)
        rendered_prompt = get_semantic_prompt(prompt_variables)

        observability = AIObservabilityService()
        ai_result = await observability.generate(
            operation="chat",
            module="semantic_intelligence",
            artifact_type="database_semantic",
            database_id=database.id,
            database_name=database.display_name or database.name,
            prompt_id=rendered_prompt.metadata.id,
            prompt_version=rendered_prompt.metadata.version,
            model_name=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": rendered_prompt.system_message
                    or (
                        "You are an Enterprise Data Architect specializing in semantic analysis. "
                        "Analyze database metadata and provide business insights. "
                        "ALWAYS respond with valid JSON only, no markdown, no explanations."
                    ),
                },
                {"role": "user", "content": rendered_prompt.user_prompt},
            ],
            request_kwargs={
                "max_completion_tokens": 4000,
                "response_format": {"type": "json_object"},
            },
            completeness_score=self._semantic_completeness(metadata_payload),
            coverage_score=self._semantic_coverage(metadata_payload),
            confidence_score=0.0,
            extra_metadata={
                "database_id": database.id,
                "database_name": database.display_name or database.name,
                "artifact_generated": "database_semantic",
            },
        )

        if ai_result.content:
            return ai_result

        logger.warning(
            "Empty OpenAI semantic response received in JSON mode for database %d; returning empty content",
            database.id,
        )
        return ai_result

    def _extract_json_payload(self, response_text: str) -> str:
        """Extract a JSON object from common model response wrappers."""
        text = (response_text or "").strip()
        if not text:
            raise ValueError("Empty response from OpenAI")

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if text.startswith("{") and text.endswith("}"):
            return text

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return text

    # ── Response parsing ───────────────────────────────────────────────────

    def _parse_enrichment_response(
        self, source_id: int, response_text: str, metadata_payload: dict[str, Any]
    ) -> DatabaseSemanticEnrichment:
        """
        Parse Azure OpenAI response into structured enrichment data.
        
        Handles malformed JSON gracefully.
        """
        try:
            clean_response = self._extract_json_payload(response_text)
            response_data = json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse OpenAI response as JSON: %s", e)
            logger.debug("Response text: %s", response_text)
            # Return minimal enrichment with raw response for debugging
            return DatabaseSemanticEnrichment(
                source_id=source_id,
                business_domain="Unknown",
                business_summary="Failed to parse AI response",
                key_entities=[],
                business_glossary=[],
                suggested_use_cases=[],
                confidence_score=0.0,
                analysis_notes=None,
                raw_response=response_text,
            )

        return DatabaseSemanticEnrichment(
            source_id=source_id,
            business_domain=response_data.get("business_domain", "Unknown"),
            business_summary=response_data.get("business_summary", ""),
            key_entities=response_data.get("key_entities", []),
            business_glossary=response_data.get("business_glossary", []),
            suggested_use_cases=response_data.get("suggested_use_cases", []),
            confidence_score=1.0,  # Will be adjusted by calculate_confidence_score
            analysis_notes=self._normalize_description(response_data.get("analysis_notes")),
            raw_response=response_text,
        )

    # ── Confidence scoring ─────────────────────────────────────────────────

    def _calculate_confidence_score(
        self, database: ConnectedDatabase, enrichment: DatabaseSemanticEnrichment
    ) -> float:
        """
        Calculate confidence score based on schema quality indicators.
        
        Factors:
        - Naming quality
        - Presence of relationships
        - Entity consistency
        
        Score: 0.0 - 1.0
        """
        score = 1.0

        # Penalty for poor naming
        naming_patterns = self._analyze_naming_patterns(database)
        if naming_patterns.get("has_poor_naming"):
            poor_ratio = naming_patterns.get("poor_naming_ratio", 0.3)
            penalty = CONFIDENCE_POOR_NAMING_PENALTY * min(poor_ratio, 1.0)
            score -= penalty
            logger.debug("Applied poor naming penalty: %.2f", penalty)

        # Penalty for missing relationships
        total_tables = sum(len(s.tables or []) for s in (database.schemas or []))
        total_relationships = sum(
            len(t.relationships_from or []) for s in (database.schemas or []) for t in (s.tables or [])
        )

        if total_tables > 0:
            relationship_ratio = total_relationships / total_tables if total_tables > 0 else 0
            if relationship_ratio < 0.3:  # Less than 0.3 relationships per table on average
                score -= CONFIDENCE_INCOMPLETE_RELATIONSHIPS_PENALTY
                logger.debug("Applied incomplete relationships penalty: %.2f", CONFIDENCE_INCOMPLETE_RELATIONSHIPS_PENALTY)

        # Ensure score stays in valid range
        return max(0.0, min(1.0, score))

    # ── Database operations ────────────────────────────────────────────────

    async def save_enrichment(
        self, enrichment: DatabaseSemanticEnrichment, status: SemanticGenerationStatus = SemanticGenerationStatus.completed
    ) -> DatabaseSemantic:
        """
        Persist enrichment to database.
        
        Creates or updates the DatabaseSemantic record.
        """
        db_semantic, _ = await self.get_or_create_semantic(
            enrichment.source_id,
            enrichment=enrichment,
            status=status,
        )

        logger.info("Saved semantic enrichment for database %d", enrichment.source_id)
        return db_semantic

    async def save_error(self, source_id: int, error_message: str) -> DatabaseSemantic:
        """Save error status for failed semantic generation."""
        db_semantic, _ = await self.get_or_create_semantic(
            source_id,
            error_message=error_message,
            status=SemanticGenerationStatus.failed,
        )
        return db_semantic

    async def get_semantic(self, source_id: int) -> Optional[DatabaseSemantic]:
        """Fetch the latest semantic profile for a database."""
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == source_id)
        )
        return result.scalars().first()

    async def delete_semantic(self, source_id: int) -> bool:
        """Delete semantic profile for a database."""
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == source_id)
        )
        db_semantic = result.scalars().first()

        if db_semantic:
            await self.db.delete(db_semantic)
            await safe_flush(self.db)
            logger.info("Deleted semantic enrichment for database %d", source_id)
            return True

        return False
