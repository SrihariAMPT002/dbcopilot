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
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    SemanticGenerationStatus,
)
from app.schema_engine.enricher import get_openai_client
from app.utils import safe_flush

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_ENTITIES_TO_SAMPLE = 50
MAX_RELATIONSHIPS_TO_SAMPLE = 100
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
        raw_response: Optional[str] = None,
    ):
        self.source_id = source_id
        self.business_domain = business_domain
        self.business_summary = business_summary
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
        self.openai_client = None

    def _get_openai_client(self):
        """Lazy-load OpenAI client with Azure configuration."""
        if self.openai_client is None:
            self.openai_client = get_openai_client()
        return self.openai_client

    def _apply_enrichment_fields(
        self,
        db_semantic: DatabaseSemantic,
        enrichment: DatabaseSemanticEnrichment,
        status: SemanticGenerationStatus,
    ) -> None:
        """Copy generated semantic values onto an ORM row."""
        db_semantic.business_domain = enrichment.business_domain
        db_semantic.business_summary = enrichment.business_summary
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
            response_text = await self._call_azure_openai(metadata_payload)
        except Exception as e:
            logger.error("Azure OpenAI call failed for database %d: %s", source_id, e, exc_info=True)
            raise

        # Parse response
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
            response_text = await self._call_azure_openai(metadata_payload)
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
        - Schemas and tables
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
            schema_info = {
                "name": schema.name,
                "tables": [],
                "table_count": len(schema.tables) if schema.tables else 0,
            }

            # Collect table information
            for table in schema.tables or []:
                table_info = {
                    "name": table.name,
                    "type": table.table_type.value if hasattr(table.table_type, "value") else str(table.table_type),
                    "row_count": table.row_count,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "is_pk": col.is_primary_key,
                            "is_fk": col.is_foreign_key,
                            "nullable": col.is_nullable,
                        }
                        for col in (table.columns or [])
                    ],
                    "relationships": [
                        {
                            "column": rel.column_name,
                            "references": f"{rel.referenced_table_name}.{rel.referenced_column_name}",
                        }
                        for rel in (table.relationships_from or [])
                    ],
                }

                schema_info["tables"].append(table_info)
                payload["total_tables"] += 1
                payload["total_relationships"] += len(table.relationships_from or [])

            payload["schemas"].append(schema_info)

        # Analyze naming patterns
        payload["naming_patterns"] = self._analyze_naming_patterns(database)

        return payload

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

    # ── Azure OpenAI Integration ───────────────────────────────────────────

    async def _call_azure_openai(self, metadata_payload: dict[str, Any]) -> str:
        """
        Call Azure OpenAI to generate semantic understanding.
        
        Returns:
            Raw response text from the model
        """
        client = self._get_openai_client()

        # Build prompt
        prompt = self._build_semantic_prompt(metadata_payload)

        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an Enterprise Data Architect specializing in semantic analysis. "
                        "Analyze database metadata and provide business insights. "
                        "ALWAYS respond with valid JSON only, no markdown, no explanations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_completion_tokens=2000,
            response_format={"type": "json_object"},  # Force JSON output
        )

        return response.choices[0].message.content

    def _build_semantic_prompt(self, metadata_payload: dict[str, Any]) -> str:
        """Build the prompt for Azure OpenAI semantic analysis."""
        prompt = f"""
Analyze the following database metadata and provide semantic business intelligence.

DATABASE METADATA:
{json.dumps(metadata_payload, indent=2)}

Based on this metadata, provide a JSON response with the following structure:
{{
  "business_domain": "Primary business domain (e.g., E-Commerce, Healthcare, Finance)",
  "business_summary": "2-3 sentence summary of the database purpose and scope",
  "key_entities": ["entity1", "entity2", "entity3", ...],
  "business_glossary": [
    {{"term": "term_name", "definition": "brief definition"}},
    ...
  ],
  "suggested_use_cases": [
    "Use case 1",
    "Use case 2",
    ...
  ]
}}

Requirements:
- Infer business domain from table/column names and structure
- Key entities should be the main business objects (e.g., customers, orders, products)
- Glossary should map technical names to business terminology
- Confidence in your analysis (higher for clear naming, lower for generic/poor naming)
- Use cases should be specific analytics or reporting possibilities
- Return ONLY valid JSON, no markdown or explanations
"""
        return prompt.strip()

    # ── Response parsing ───────────────────────────────────────────────────

    def _parse_enrichment_response(
        self, source_id: int, response_text: str, metadata_payload: dict[str, Any]
    ) -> DatabaseSemanticEnrichment:
        """
        Parse Azure OpenAI response into structured enrichment data.
        
        Handles malformed JSON gracefully.
        """
        try:
            response_data = json.loads(response_text)
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
