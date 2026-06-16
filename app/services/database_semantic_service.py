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
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.config.manager import get_config_manager
from app.config.prompts import get_semantic_prompt
from app.config.prompts import get_prompt_registry
from app.config.package_registry import package_is_enabled
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    SemanticPackage,
    TableSemanticPackage,
    SemanticEvidence,
    BusinessGlossary,
    SemanticGenerationStatus,
)
from app.services.database_guard import ensure_connected
from app.schema_engine.embeddings import _traceable
from app.models.metadata import SchemaSemantic
from app.services.ai_observability_service import AIObservabilityService, AIObservationResult
from app.services.column_semantic_service import ColumnSemanticService
from app.services.semantic_feature_service import SemanticFeatureService
from app.services.domain_inference_service import DomainInferenceService
from app.services.semantic_validator_service import SemanticValidatorService
from app.services.business_glossary_service import BusinessGlossaryService
from app.services.schema_chunking_service import SchemaChunkingService
from app.utils import safe_flush

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_TABLES_IN_PACKAGE = 40
MAX_SCHEMAS_IN_PACKAGE = 8
MAX_RELATIONSHIPS_IN_PACKAGE = 120
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
        business_processes: list[str] | None = None,
        table_semantics: list[dict[str, Any]] | None = None,
        domain_scores: dict[str, float] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        analysis_notes: Optional[str] = None,
        raw_response: Optional[str] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        self.source_id = source_id
        self.business_domain = business_domain
        self.business_summary = business_summary
        self.analysis_notes = analysis_notes
        self.key_entities = key_entities
        self.business_glossary = business_glossary
        self.suggested_use_cases = suggested_use_cases
        self.business_processes = business_processes or []
        self.table_semantics = table_semantics or []
        self.domain_scores = domain_scores or {}
        self.evidence = evidence or []
        self.confidence_score = confidence_score
        self.raw_response = raw_response
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.model_name = model_name
        self.trace_id = trace_id
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
        self.feature_service = SemanticFeatureService(db)
        self.domain_inference = DomainInferenceService()
        self.semantic_validator = SemanticValidatorService()
        self.glossary_service = BusinessGlossaryService()
        self.chunker = SchemaChunkingService(
            max_schemas=MAX_SCHEMAS_IN_PACKAGE,
            max_tables_per_schema=MAX_TABLES_IN_PACKAGE,
            max_columns_per_table=12,
        )

    @staticmethod
    def _trace_id_as_string(trace_id: Any) -> str | None:
        if trace_id is None:
            return None
        return str(trace_id)

    def _apply_enrichment_fields(
        self,
        db_semantic: DatabaseSemantic,
        enrichment: DatabaseSemanticEnrichment,
        status: SemanticGenerationStatus,
        *,
        execution_status: str | None = "success",
        fallback_used: bool = False,
        retry_count: int = 0,
        trace_id: str | None = None,
    ) -> None:
        """Copy generated semantic values onto an ORM row."""
        db_semantic.business_domain = enrichment.business_domain
        db_semantic.business_summary = enrichment.business_summary
        db_semantic.analysis_notes = enrichment.analysis_notes
        db_semantic.key_entities = enrichment.key_entities
        db_semantic.business_glossary = enrichment.business_glossary
        db_semantic.suggested_use_cases = enrichment.suggested_use_cases
        db_semantic.business_processes = enrichment.business_processes
        db_semantic.confidence_score = enrichment.confidence_score
        db_semantic.raw_ai_response = enrichment.raw_response
        db_semantic.error_message = None
        db_semantic.generation_status = status
        db_semantic.execution_status = execution_status
        db_semantic.used_fallback = fallback_used
        db_semantic.retry_count = retry_count
        db_semantic.trace_id = self._trace_id_as_string(trace_id or getattr(enrichment, "trace_id", None))
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
        db_semantic.business_processes = []
        db_semantic.confidence_score = 0.0
        db_semantic.raw_ai_response = None
        db_semantic.error_message = error_message
        db_semantic.generation_status = status
        db_semantic.execution_status = "failed"
        db_semantic.used_fallback = False
        db_semantic.retry_count = 0
        db_semantic.trace_id = None
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
        db_semantic.execution_status = "failed"
        db_semantic.used_fallback = False
        db_semantic.retry_count = 0
        db_semantic.trace_id = None
        db_semantic.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _fingerprint_payload(payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:32]

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
        if await self._schema_count(source_id) <= 0:
            logger.warning("Database %d has no schemas", source_id)
            raise ValueError("no_metadata")

        semantic_input = await self._build_semantic_input(database)

        logger.info("Generating semantics for database %d", source_id)

        # Call Azure OpenAI
        try:
            ai_result = await self._call_azure_openai(database, semantic_input)
        except Exception as e:
            logger.error("Azure OpenAI call failed for database %d: %s", source_id, e, exc_info=True)
            raise

        # Parse response
        response_text = ai_result.content or ""
        enrichment = self._parse_enrichment_response(source_id, response_text)
        enrichment.trace_id = self._trace_id_as_string(getattr(ai_result, "trace_id", None))
        enrichment.confidence_score = await self._calculate_confidence_score(database, enrichment)

        logger.info(
            "Completed semantic generation for database %d with confidence %.2f",
            source_id,
            enrichment.confidence_score,
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
        if not package_is_enabled("semantic"):
            raise ValueError("Semantic package is disabled by registry")

        database = await self._fetch_database_with_metadata(source_id)
        if not database:
            raise ValueError(f"Database {source_id} not found")

        semantic_row, _ = await self.get_or_create_semantic(
            source_id,
            status=SemanticGenerationStatus.processing,
        )

        try:
            if await self._schema_count(source_id) <= 0:
                logger.warning("Database %d has no schemas", source_id)
                semantic_row, _ = await self.get_or_create_semantic(
                    source_id,
                    status=SemanticGenerationStatus.no_metadata,
                    error_message="No metadata available in database",
                )
                return semantic_row, (time.time() - start_time) * 1000

            semantic_input = await self._build_semantic_input(database)
            logger.info("Generating semantics for database %d", source_id)
            ai_result = await self._call_azure_openai(database, semantic_input)
            response_text = ai_result.content or ""
            if not response_text.strip():
                logger.warning("Empty semantic response for database %d; persisting failed semantic state", source_id)
                semantic_row, _ = await self.get_or_create_semantic(
                    source_id,
                    status=SemanticGenerationStatus.failed,
                    error_message="empty_ai_response",
                )
                raise ValueError("empty_ai_response")
            enrichment = self._parse_enrichment_response(source_id, response_text)
            enrichment.confidence_score = await self._calculate_confidence_score(database, enrichment)
            enrichment.trace_id = self._trace_id_as_string(getattr(ai_result, "trace_id", None))
            enrichment.prompt_id = getattr(ai_result, "prompt_id", None)
            enrichment.prompt_version = getattr(ai_result, "prompt_version", None)
            enrichment.model_name = getattr(ai_result, "model_name", None)

            semantic_row = await self.save_enrichment(enrichment, SemanticGenerationStatus.completed)
            await self._upsert_semantic_package(enrichment)
            await self._persist_semantic_evidence(enrichment)
            await self._persist_business_glossary(enrichment)
            return semantic_row, (time.time() - start_time) * 1000

        except ValueError as exc:
            logger.error("Semantic generation failed for database %d: %s", source_id, exc, exc_info=True)
            semantic_row, _ = await self.get_or_create_semantic(
                source_id,
                status=SemanticGenerationStatus.failed,
                error_message=str(exc),
            )
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
            .options(
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.columns),
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.relationships_from),
                selectinload(ConnectedDatabase.schemas)
                .selectinload(DatabaseSchema.tables)
                .selectinload(DatabaseTable.embedding),
            )
            .where(ConnectedDatabase.id == source_id)
        )
        database = result.scalars().unique().first()
        if not database:
            return None
        return database

    async def _fetch_schemas(self, database_id: int) -> list[DatabaseSchema]:
        result = await self.db.execute(
            select(DatabaseSchema)
            .options(
                selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.columns),
                selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().unique().all())

    # ── Semantic package input ─────────────────────────────────────────────

    async def _build_semantic_input(self, database: ConnectedDatabase) -> dict[str, Any]:
        """Build compact metadata + governance package input for business intelligence generation."""
        governance_package = await ColumnSemanticService(self.db).build_governance_package(database.id)
        pii_map = await ColumnSemanticService(self.db).get_pii_map(database.id)
        schema_count = await self._schema_count(database.id)
        table_map = await self._table_name_map(database.id)
        relationships_result = await self.db.execute(
            select(DatabaseRelationship).join(DatabaseTable, DatabaseRelationship.table_id == DatabaseTable.id)
        )
        relationships = relationships_result.scalars().all()
        relationship_samples = relationships[:MAX_RELATIONSHIPS_IN_PACKAGE]
        domain_scores = self.domain_inference.infer(
            governance_package=governance_package,
            relationship_context=[
                {"source_table": table_map.get(rel.table_id), "target_table": rel.referenced_table_name}
                for rel in relationship_samples
            ],
            statistics={"schema_count": schema_count},
        )

        hierarchical_context = self.chunker.build(database, pii_map=pii_map)
        metadata = {
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "schema_count": hierarchical_context["totals"]["schema_count"],
            "table_count": hierarchical_context["totals"]["table_count"],
            "column_count": hierarchical_context["totals"]["column_count"],
            "relationship_count": hierarchical_context["totals"]["relationship_count"],
            "relationship_chunk_count": (len(relationships) + MAX_RELATIONSHIPS_IN_PACKAGE - 1) // MAX_RELATIONSHIPS_IN_PACKAGE if relationships else 0,
            "relationship_truncated": len(relationships) > MAX_RELATIONSHIPS_IN_PACKAGE,
            "naming_patterns": await self._analyze_naming_patterns(database.id),
            "schema_summaries": hierarchical_context["schema_summaries"],
            "schema_chunk_count": hierarchical_context["schema_chunk_count"],
            "truncated": hierarchical_context["truncated"],
        }
        return {
            "metadata": metadata,
            "governance_package": governance_package,
            "relationships": [
                {
                    "table_id": rel.table_id,
                    "referenced_table_name": rel.referenced_table_name,
                    "column_name": rel.column_name,
                    "referenced_column_name": rel.referenced_column_name,
                }
                for rel in relationship_samples
            ],
            "domain_scores": domain_scores,
            "relationship_summary": {
                "total_relationships": len(relationships),
                "sampled_relationships": len(relationship_samples),
                "truncated": len(relationships) > MAX_RELATIONSHIPS_IN_PACKAGE,
            },
        }

    @staticmethod
    def _normalize_description(description: Optional[str]) -> Optional[str]:
        """Return a trimmed catalog description, or None when empty."""
        if not description:
            return None
        text = description.strip()
        return text or None

    async def _analyze_naming_patterns(self, database_id: int) -> dict[str, Any]:
        """Analyze naming patterns to assess metadata quality."""
        patterns = {
            "table_prefixes": set(),
            "has_poor_naming": False,
            "has_consistent_naming": True,
        }

        poor_naming_count = 0
        total_tables = 0

        schemas = await self._fetch_schemas(database_id)
        for schema in schemas:
            for table in schema.tables or []:
                total_tables += 1
                if self._is_poor_name(table.name):
                    poor_naming_count += 1
                parts = table.name.split("_")
                if len(parts) > 1:
                    patterns["table_prefixes"].add(parts[0])

        patterns["table_prefixes"] = list(patterns["table_prefixes"])

        if total_tables > 0:
            poor_naming_ratio = poor_naming_count / total_tables
            patterns["has_poor_naming"] = poor_naming_ratio > 0.3
            patterns["poor_naming_ratio"] = poor_naming_ratio

        return patterns

    async def _schema_count(self, database_id: int) -> int:
        result = await self.db.execute(
            select(func.count(DatabaseSchema.id)).where(DatabaseSchema.connected_db_id == database_id)
        )
        return int(result.scalar_one() or 0)

    async def _fetch_schemas(self, database_id: int) -> list[DatabaseSchema]:
        result = await self.db.execute(
            select(DatabaseSchema)
            .options(
                selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.columns),
                selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.relationships_from),
            )
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().unique().all())

    async def _table_name_map(self, database_id: int) -> dict[int, str]:
        result = await self.db.execute(
            select(DatabaseTable.id, DatabaseTable.name)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(DatabaseSchema.connected_db_id == database_id)
        )
        return {int(table_id): str(name) for table_id, name in result.all()}

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

    @staticmethod
    def _semantic_completeness(semantic_input: dict[str, Any]) -> float:
        metadata = semantic_input.get("metadata") or {}
        governance = semantic_input.get("governance_package") or {}
        total_tables = int(metadata.get("table_count", 0) or 0)
        if total_tables <= 0:
            return 0.0
        score = 0.4
        if int(metadata.get("relationship_count", 0) or 0) > 0:
            score += 0.2
        if governance.get("packages"):
            score += 0.4
        return round(min(1.0, score), 3)

    @staticmethod
    def _semantic_coverage(semantic_input: dict[str, Any]) -> float:
        metadata = semantic_input.get("metadata") or {}
        tables = int(metadata.get("table_count", 0) or 0)
        governed = int((semantic_input.get("governance_package") or {}).get("table_count", 0) or 0)
        if tables <= 0:
            return 0.0
        return round(min(1.0, governed / tables), 3)

    def _build_prompt_variables(self, database: ConnectedDatabase, semantic_input: dict[str, Any]) -> dict[str, Any]:
        """Build variables for the metadata + governance semantic prompt."""
        return {
            "metadata": semantic_input.get("metadata") or {},
            "governance_package": semantic_input.get("governance_package") or {},
            "relationships": semantic_input.get("relationships") or [],
            "relationship_summary": semantic_input.get("relationship_summary") or {},
            "domain_scores": semantic_input.get("domain_scores") or {},
            "database_name": database.display_name or database.name,
        }

    @staticmethod
    def _build_system_prompt_variables(database: ConnectedDatabase, semantic_input: dict[str, Any]) -> dict[str, Any]:
        semantic = semantic_input.get("semantic") or semantic_input.get("database_semantic") or {
            "business_domain": semantic_input.get("business_domain") or None,
            "business_summary": semantic_input.get("business_summary") or None,
            "key_entities": semantic_input.get("key_entities") or [],
            "business_glossary": semantic_input.get("business_glossary") or [],
            "business_processes": semantic_input.get("business_processes") or [],
        }
        governance = semantic_input.get("governance_package") or {}
        relationship_intelligence = semantic_input.get("relationship_intelligence") or {}
        return {
            "database_name": database.display_name or database.name,
            "database_type": database.db_type.value,
            "semantic": semantic,
            "governance": {
                "prompt_protection_enabled": bool(semantic_input.get("prompt_protection_enabled", False)),
                "embedding_protection_enabled": bool(semantic_input.get("embedding_protection_enabled", False)),
                "pii_coverage": float(governance.get("pii_identified_coverage", 0.0) or 0.0),
            },
            "relationship_intelligence": relationship_intelligence,
            "domain_scores": semantic_input.get("domain_scores") or {},
        }

    @_traceable("database_semantic_openai_call", run_type="llm")
    async def _call_azure_openai(self, database: ConnectedDatabase, semantic_input: dict[str, Any]) -> AIObservationResult:
        """
        Call Azure OpenAI to generate semantic understanding.

        Returns:
            AIObservationResult with response text, token usage, and trace metadata.
        """
        prompt_variables = self._build_prompt_variables(database, semantic_input)
        rendered_prompt = get_semantic_prompt(prompt_variables)

        observability = AIObservabilityService()
        max_completion_tokens = int(get_config_manager().get_model_config("semantic_generation").get("max_completion_tokens", 2000) or 2000)
        system_prompt = get_prompt_registry().render_prompt(
            "system_prompt",
            self._build_system_prompt_variables(database, semantic_input),
            category="system",
        ).system_message
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
                    "content": rendered_prompt.system_message or system_prompt,
                },
                {"role": "user", "content": rendered_prompt.user_prompt},
            ],
            request_kwargs={
                "max_completion_tokens": max_completion_tokens,
                "response_format": {"type": "json_object"},
                "reasoning_effort": "low",
            },
            completeness_score=self._semantic_completeness(semantic_input),
            coverage_score=self._semantic_coverage(semantic_input),
            confidence_score=0.0,
            execution_status="success",
            fallback_used=False,
            retry_count=0,
            extra_metadata={
                "database_id": database.id,
                "job_id": None,
                "stage": "semantics",
                "database_name": database.display_name or database.name,
                "artifact_generated": "database_semantic",
                "metadata_fingerprint": self._fingerprint_payload(semantic_input),
                "parse_success": True,
            },
        )

        if ai_result.content:
            return ai_result

        logger.warning(
            "Empty OpenAI semantic response received in JSON mode for database %d; returning empty content",
            database.id,
        )
        raise ValueError("empty_ai_response")

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

    def _parse_enrichment_response(self, source_id: int, response_text: str) -> DatabaseSemanticEnrichment:
        """Parse Azure OpenAI semantic package response."""
        clean_response = self._extract_json_payload(response_text)
        if not clean_response.strip():
            raise ValueError("empty_ai_response")
        try:
            response_data = json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse OpenAI response as JSON: %s", e)
            raise ValueError("invalid_json") from e
        if not isinstance(response_data, dict):
            raise ValueError("invalid_json")

        semantic_summary = response_data.get("semantic_summary") or response_data.get("business_summary") or ""
        business_entities = response_data.get("business_entities") or response_data.get("key_entities") or []
        business_capabilities = response_data.get("business_capabilities") or response_data.get("suggested_use_cases") or []
        business_processes = response_data.get("business_processes") or []
        payload = self.semantic_validator.parse_and_validate(json.dumps({
            "business_domain": response_data.get("business_domain", "Unknown"),
            "semantic_summary": semantic_summary,
            "business_entities": business_entities,
            "business_capabilities": business_capabilities,
            "business_processes": business_processes,
            "table_semantics": response_data.get("table_semantics") or [],
        }))

        return DatabaseSemanticEnrichment(
            source_id=source_id,
            business_domain=payload.get("business_domain", "Unknown"),
            business_summary=semantic_summary,
            key_entities=list(business_entities),
            business_glossary=response_data.get("business_glossary", []),
            suggested_use_cases=list(business_capabilities),
            business_processes=list(business_processes),
            table_semantics=list(response_data.get("table_semantics") or []),
            confidence_score=1.0,
            domain_scores=response_data.get("domain_scores") or {},
            evidence=response_data.get("evidence") or [],
            analysis_notes=self._normalize_description(response_data.get("analysis_notes")),
            raw_response=response_text,
            trace_id=None,
        )

    async def _save_table_semantics(
        self,
        database: ConnectedDatabase,
        table_semantics: list[dict[str, Any]],
    ) -> None:
        """Persist table-level semantic packages to schema_semantics."""
        if not table_semantics:
            return

        table_lookup: dict[tuple[str, str], DatabaseTable] = {}
        schemas = await self._fetch_schemas(database.id)
        for schema in schemas:
            for table in schema.tables or []:
                table_lookup[(schema.name, table.name)] = table

        for item in table_semantics:
            schema_name = str(item.get("schema_name") or "")
            table_name = str(item.get("table_name") or "")
            table = table_lookup.get((schema_name, table_name))
            if table is None:
                continue

            result = await self.db.execute(
                select(SchemaSemantic).where(SchemaSemantic.table_id == table.id)
            )
            row = result.scalars().first()
            if row is None:
                row = SchemaSemantic(
                    database_id=database.id,
                    table_id=table.id,
                    semantic_summary=str(item.get("semantic_summary") or f"{schema_name}.{table_name}"),
                )
                self.db.add(row)

            row.semantic_summary = str(item.get("semantic_summary") or row.semantic_summary)
            row.business_capabilities = list(item.get("business_capabilities") or [])
            row.business_entities = list(item.get("business_entities") or [])
            row.business_processes = list(item.get("business_processes") or [])
            row.business_keywords = list(item.get("business_entities") or [])[:10]
            row.possible_questions = [
                f"What business process uses {table_name}?",
                f"Which entities are modeled in {table_name}?",
            ]
            row.updated_at = datetime.now(timezone.utc)

        await safe_flush(self.db)

    async def _upsert_semantic_package(self, enrichment: DatabaseSemanticEnrichment) -> SemanticPackage:
        result = await self.db.execute(
            select(SemanticPackage).where(SemanticPackage.database_id == enrichment.source_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = SemanticPackage(database_id=enrichment.source_id)
            self.db.add(row)
        row.business_domain = enrichment.business_domain
        row.semantic_summary = enrichment.business_summary
        row.business_entities = enrichment.key_entities
        row.business_processes = enrichment.business_processes
        row.business_capabilities = enrichment.suggested_use_cases
        row.business_glossary = enrichment.business_glossary
        row.confidence_score = enrichment.confidence_score
        row.domain_scores = enrichment.domain_scores
        row.evidence = enrichment.evidence
        row.prompt_id = getattr(enrichment, "prompt_id", None)
        row.prompt_version = getattr(enrichment, "prompt_version", None)
        row.model_name = getattr(enrichment, "model_name", None)
        row.trace_id = self._trace_id_as_string(enrichment.trace_id)
        row.updated_at = datetime.now(timezone.utc)
        await safe_flush(self.db)
        return row

    async def _update_semantic_package(self, enrichment: DatabaseSemanticEnrichment) -> SemanticPackage:
        return await self._upsert_semantic_package(enrichment)

    async def _persist_semantic_evidence(self, enrichment: DatabaseSemanticEnrichment) -> None:
        result = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == enrichment.source_id))
        package = result.scalar_one_or_none()
        if package is None:
            return
        rows: list[SemanticEvidence] = []
        for item in enrichment.evidence or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                SemanticEvidence(
                    semantic_package_id=package.id,
                    evidence_type=str(item.get("source") or "semantic"),
                    evidence_source="azure_openai",
                    evidence_json=json.dumps(item, default=str),
                )
            )
        if rows:
            self.db.add_all(rows)
            await safe_flush(self.db)

    async def _persist_business_glossary(self, enrichment: DatabaseSemanticEnrichment) -> None:
        result = await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == enrichment.source_id))
        package = result.scalar_one_or_none()
        if package is None:
            return
        rows: list[BusinessGlossary] = []
        for term in self.glossary_service.build_glossary(
            business_entities=enrichment.key_entities,
            business_processes=enrichment.business_processes,
            business_capabilities=enrichment.suggested_use_cases,
        ):
            rows.append(
                BusinessGlossary(
                    semantic_package_id=package.id,
                    term=str(term.get("term") or ""),
                    definition=str(term.get("definition") or ""),
                    source=str(term.get("source") or "ai"),
                    confidence_score=float(enrichment.confidence_score or 0.0),
                )
            )
        if rows:
            self.db.add_all(rows)
            await safe_flush(self.db)

    async def get_semantic_evidence(self, source_id: int) -> dict[str, Any]:
        package = await self.get_semantic_package(source_id)
        result = await self.db.execute(
            select(SemanticEvidence)
            .join(SemanticPackage, SemanticEvidence.semantic_package_id == SemanticPackage.id)
            .where(SemanticPackage.database_id == source_id)
            .order_by(SemanticEvidence.created_at)
        )
        rows = result.scalars().all()
        return {
            "database_id": source_id,
            "business_domain": package.get("business_domain"),
            "confidence_score": package.get("confidence_score", 0.0),
            "domain_scores": package.get("domain_scores", {}),
            "evidence": [
                {
                    "id": row.id,
                    "semantic_package_id": row.semantic_package_id,
                    "table_id": row.table_id,
                    "evidence_type": row.evidence_type,
                    "evidence_source": row.evidence_source,
                    "evidence_json": json.loads(row.evidence_json or "{}"),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
        }

    async def _upsert_table_semantic_package(
        self,
        database: ConnectedDatabase,
        semantic: SchemaSemantic,
        table: DatabaseTable,
        *,
        prompt_id: str | None,
        prompt_version: str | None,
        model_name: str | None,
        trace_id: str | None,
    ) -> TableSemanticPackage:
        result = await self.db.execute(
            select(TableSemanticPackage).where(TableSemanticPackage.table_id == table.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = TableSemanticPackage(database_id=database.id, table_id=table.id)
            self.db.add(row)
        row.business_purpose = semantic.semantic_summary
        row.business_entity = ", ".join(semantic.business_entities or [])
        row.business_capability = ", ".join(semantic.business_capabilities or [])
        row.business_process = ", ".join(semantic.business_processes or [])
        row.business_keywords = list(semantic.business_entities or [])[:10]
        row.semantic_summary = semantic.semantic_summary
        row.confidence_score = 1.0
        row.prompt_id = prompt_id
        row.prompt_version = prompt_version
        row.model_name = model_name
        row.trace_id = self._trace_id_as_string(trace_id)
        row.updated_at = datetime.now(timezone.utc)
        await safe_flush(self.db)
        return row

    # ── Confidence scoring ─────────────────────────────────────────────────

    async def _calculate_confidence_score(
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
        naming_patterns = await self._analyze_naming_patterns(database.id)
        if naming_patterns.get("has_poor_naming"):
            poor_ratio = naming_patterns.get("poor_naming_ratio", 0.3)
            penalty = CONFIDENCE_POOR_NAMING_PENALTY * min(poor_ratio, 1.0)
            score -= penalty
            logger.debug("Applied poor naming penalty: %.2f", penalty)

        # Penalty for missing relationships
        schemas = await self._fetch_schemas(database.id)
        total_tables = sum(len(s.tables or []) for s in schemas)
        total_relationships = sum(len(t.relationships_from or []) for s in schemas for t in (s.tables or []))

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

        if enrichment.table_semantics:
            database = await self._fetch_database_with_metadata(enrichment.source_id)
            if database:
                await self._save_table_semantics(database, enrichment.table_semantics)
                for item in enrichment.table_semantics:
                    schema_name = str(item.get("schema_name") or "")
                    table_name = str(item.get("table_name") or "")
                    schemas = await self._fetch_schemas(database.id)
                    table = next(
                        (
                            tbl
                            for schema in schemas
                            for tbl in schema.tables or []
                            if schema.name == schema_name and tbl.name == table_name
                        ),
                        None,
                    )
                    if table is None:
                        continue
                    result = await self.db.execute(
                        select(SchemaSemantic).where(SchemaSemantic.table_id == table.id)
                    )
                    semantic_row = result.scalars().first()
                    if semantic_row is not None:
                        await self._upsert_table_semantic_package(
                            database,
                            semantic_row,
                            table,
                            prompt_id=getattr(enrichment, "prompt_id", None),
                            prompt_version=getattr(enrichment, "prompt_version", None),
                            model_name=getattr(enrichment, "model_name", None),
                            trace_id=enrichment.trace_id,
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

    async def build_semantic_package(self, source_id: int) -> dict[str, Any]:
        """Build the persisted semantic package for downstream consumers."""
        db_semantic = await self.get_semantic(source_id)
        if not db_semantic:
            return {
                "database_id": source_id,
                "business_domain": None,
                "business_summary": None,
                "business_capabilities": [],
                "business_entities": [],
                "business_processes": [],
                "semantic_summary": None,
                "analysis_notes": None,
                "table_semantics": [],
            }

        return {
            "database_id": source_id,
            "business_domain": db_semantic.business_domain,
            "business_summary": db_semantic.business_summary,
            "business_capabilities": db_semantic.suggested_use_cases,
            "business_entities": db_semantic.key_entities,
            "business_processes": db_semantic.business_processes,
            "semantic_summary": db_semantic.business_summary,
            "analysis_notes": db_semantic.analysis_notes,
            "confidence_score": float(db_semantic.confidence_score or 0.0),
            "domain_scores": db_semantic.domain_scores if hasattr(db_semantic, "domain_scores") else {},
            "evidence": db_semantic.evidence if hasattr(db_semantic, "evidence") else [],
            "prompt_id": db_semantic.prompt_id if hasattr(db_semantic, "prompt_id") else None,
            "prompt_version": db_semantic.prompt_version if hasattr(db_semantic, "prompt_version") else None,
            "model_name": db_semantic.model_name if hasattr(db_semantic, "model_name") else None,
            "trace_id": db_semantic.trace_id if hasattr(db_semantic, "trace_id") else None,
            "table_semantics": await self._load_table_semantics(source_id),
        }

    async def _load_table_semantics(self, source_id: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(SchemaSemantic, DatabaseTable, DatabaseSchema)
            .join(DatabaseTable, SchemaSemantic.table_id == DatabaseTable.id)
            .join(DatabaseSchema, DatabaseTable.schema_id == DatabaseSchema.id)
            .where(SchemaSemantic.database_id == source_id)
            .order_by(DatabaseSchema.name, DatabaseTable.name)
        )
        return [
            {
                "schema_name": schema.name,
                "table_name": table.name,
                "semantic_summary": semantic.semantic_summary,
                "business_capabilities": semantic.business_capabilities,
                "business_entities": semantic.business_entities,
                "business_processes": semantic.business_processes,
            }
            for semantic, table, schema in result.all()
        ]

    async def get_semantic(self, source_id: int) -> Optional[DatabaseSemantic]:
        """Fetch the latest semantic profile for a database."""
        result = await self.db.execute(
            select(DatabaseSemantic).where(DatabaseSemantic.source_id == source_id)
        )
        return result.scalars().first()

    async def get_semantic_package(self, source_id: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(SemanticPackage).where(SemanticPackage.database_id == source_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return {
                "database_id": source_id,
                "business_domain": None,
                "semantic_summary": None,
                "business_entities": [],
                "business_processes": [],
                "business_capabilities": [],
                "business_glossary": [],
            }
        return {
            "database_id": row.database_id,
            "business_domain": row.business_domain,
            "semantic_summary": row.semantic_summary,
            "business_entities": row.business_entities,
            "business_processes": row.business_processes,
            "business_capabilities": row.business_capabilities,
            "business_glossary": row.business_glossary,
            "confidence_score": float(row.confidence_score or 0.0),
            "prompt_id": row.prompt_id,
            "prompt_version": row.prompt_version,
            "model_name": row.model_name,
            "trace_id": row.trace_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def get_semantic_entities(self, source_id: int) -> list[str]:
        return list((await self.get_semantic_package(source_id)).get("business_entities", []))

    async def get_semantic_processes(self, source_id: int) -> list[str]:
        return list((await self.get_semantic_package(source_id)).get("business_processes", []))

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
