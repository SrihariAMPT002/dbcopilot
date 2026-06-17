"""
SchemaEnricher — Semantic enrichment using Azure OpenAI.

Converts raw schema metadata into AI-understandable business context:
- Business summary
- Likely usage patterns  
- Important columns
- Possible analytics questions
- Business keywords
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
)
from app.config.prompts import get_enrichment_prompt
from app.schema_engine.metrics import MetricsEngine
from app.services.ai_observability_service import AIObservabilityService
from app.utils import safe_flush

logger = logging.getLogger(__name__)

# ── Azure OpenAI Client (lazy initialization) ────────────────────────────────

# ── Semantic Enrichment Data Model ───────────────────────────────────────────

class SemanticEnrichment:
    """Container for enriched semantic data."""

    def __init__(
        self,
        table_id: int,
        database_id: int,
        business_summary: str,
        likely_usage: list[str],
        important_columns: list[str],
        business_keywords: list[str],
        possible_questions: list[str],
        raw_response: Optional[str] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.table_id = table_id
        self.database_id = database_id
        self.business_summary = business_summary
        self.likely_usage = likely_usage
        self.important_columns = important_columns
        self.business_keywords = business_keywords
        self.possible_questions = possible_questions
        self.raw_response = raw_response
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.model_name = model_name
        self.generated_at = datetime.now(timezone.utc)


# ── SchemaEnricher ───────────────────────────────────────────────────────────

class SchemaEnricher:
    """
    Enriches raw schema metadata with semantic business context using Azure OpenAI.
    
    Usage:
        enricher = SchemaEnricher(db_session)
        enrichment = await enricher.enrich_table(table_id)
        await enricher.save_enrichment(enrichment)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.metrics = MetricsEngine()

    # ── Main enrichment method ─────────────────────────────────────────────

    async def enrich_table(self, table_id: int) -> SemanticEnrichment:
        """
        Enrich a single table with semantic context.
        
        Args:
            table_id: Primary key of the table to enrich
            
        Returns:
            SemanticEnrichment object with business context
            
        Raises:
            ValueError: If table not found
        """
        start_time = time.time()

        # Fetch table with relationships
        table = await self._fetch_table_with_context(table_id)
        if not table:
            raise ValueError(f"Table {table_id} not found")

        # Build schema context document
        context_doc = await self._build_context_document(table)

        # Call Azure OpenAI
        try:
            ai_result = await self._call_azure_openai(table, context_doc)
            self.metrics.record_openai_call(time.time() - start_time)
        except Exception as e:
            logger.error("Azure OpenAI call failed: %s", e, exc_info=True)
            self.metrics.record_openai_error()
            raise

        # Parse response
        enrichment = self._parse_enrichment_response(table_id, table.schema.connected_db_id, ai_result.content or "")
        enrichment.prompt_id = ai_result.prompt_id
        enrichment.prompt_version = ai_result.prompt_version
        enrichment.model_name = ai_result.model_name

        # Record metrics
        self.metrics.record_enrichment_latency(time.time() - start_time)

        return enrichment

    # ── Batch enrichment (for entire database) ─────────────────────────────

    async def enrich_database(self, database_id: int) -> list[SemanticEnrichment]:
        """
        Enrich all tables in a database with semantic context.
        
        Args:
            database_id: Primary key of the connected database
            
        Returns:
            List of enriched tables
        """
        # Fetch all tables for this database
        from sqlalchemy import select

        result = await self.db.execute(
            select(DatabaseTable).join(DatabaseSchema).where(
                DatabaseSchema.connected_db_id == database_id
            )
        )
        tables = result.scalars().all()

        logger.info("Starting semantic enrichment for %d tables in database %d", len(tables), database_id)

        enrichments = []
        for table in tables:
            try:
                enrichment = await self.enrich_table(table.id)
                enrichments.append(enrichment)
            except Exception as e:
                logger.warning("Failed to enrich table %s: %s", table.name, e)
                continue

        return enrichments

    # ── Fetch table with context ───────────────────────────────────────────

    async def _fetch_table_with_context(self, table_id: int) -> Optional[DatabaseTable]:
        """Fetch table with all relationships loaded."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(DatabaseTable)
            .where(DatabaseTable.id == table_id)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
                selectinload(DatabaseTable.relationships_from),
            )
        )
        return result.scalars().unique().first()

    # ── Build context document for OpenAI ──────────────────────────────────

    async def _build_context_document(self, table: DatabaseTable) -> str:
        """
        Build a comprehensive document describing the table structure and context.
        
        This document is sent to Azure OpenAI for semantic analysis.
        """
        doc_lines = [
            f"Table Name: {table.name}",
            f"Schema: {table.schema.name}",
            f"Type: {table.table_type.value}",
            f"Row Count: {table.row_count or 'Unknown'}",
        ]

        if table.description:
            doc_lines.append(f"Description: {table.description}")

        # ── Columns ───────────────────────────────────────────────────────
        doc_lines.append("\nColumns:")
        for col in sorted(table.columns or [], key=lambda c: c.ordinal_position or 0):
            col_info = f"  - {col.name} ({col.data_type})"
            if col.is_primary_key:
                col_info += " [PRIMARY KEY]"
            if col.is_foreign_key:
                col_info += " [FOREIGN KEY]"
            if col.is_unique:
                col_info += " [UNIQUE]"
            if not col.is_nullable:
                col_info += " [NOT NULL]"
            if col.description:
                col_info += f" — {col.description}"
            doc_lines.append(col_info)

        # ── Relationships ──────────────────────────────────────────────────
        if table.relationships_from:
            doc_lines.append("\nOutgoing Relationships:")
            for rel in table.relationships_from:
                rel_info = (
                    f"  - {rel.column_name} → {rel.referenced_table_name}.{rel.referenced_column_name}"
                )
                doc_lines.append(rel_info)

        # ── Sample data context ────────────────────────────────────────────
        doc_lines.append("\n---")
        doc_lines.append("Based on the above schema, analyze and provide semantic context.")

        return "\n".join(doc_lines)

    @staticmethod
    def _schema_completeness(table: DatabaseTable) -> float:
        columns = len(table.columns or [])
        relationships = len(table.relationships_from or [])
        if columns <= 0:
            return 0.0
        score = 0.55
        if table.description:
            score += 0.20
        if relationships > 0:
            score += 0.25
        return round(min(1.0, score), 3)

    @staticmethod
    def _schema_coverage(table: DatabaseTable) -> float:
        columns = len(table.columns or [])
        if columns <= 0:
            return 0.0
        descriptive_columns = sum(1 for column in table.columns or [] if column.description)
        return round(min(1.0, (descriptive_columns / columns) if columns else 0.0), 3)

    # ── Call Azure OpenAI ──────────────────────────────────────────────────

    async def _call_azure_openai(self, table: DatabaseTable, context_doc: str):
        """
        Call Azure OpenAI GPT-4o to generate semantic enrichment.

        Uses the shared observability wrapper so the call is traced in LangSmith.
        """
        rendered_prompt = get_enrichment_prompt(
            {
                "table_name": table.name,
                "schema_name": table.schema.name,
                "table_type": table.table_type.value,
                "row_count": table.row_count or "Unknown",
                "description": table.description or "",
                "columns": [
                    {
                        "name": column.name,
                        "type": column.data_type,
                        "description": column.description or "",
                    }
                for column in table.columns or []
                ],
                "relationships": [
                    {
                        "column": rel.column_name,
                        "references": f"{rel.referenced_table_name}.{rel.referenced_column_name}",
                    }
                    for rel in table.relationships_from or []
                ],
                "context_doc": context_doc,
            }
        )

        observability = AIObservabilityService()
        return await observability.generate(
            operation="chat",
            module="semantic_intelligence",
            artifact_type="schema_semantic",
            database_id=table.schema.connected_db_id,
            database_name=table.schema.connected_database.display_name or table.schema.connected_database.name,
            prompt_id=rendered_prompt.metadata.id,
            prompt_version=rendered_prompt.metadata.version,
            model_name=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "system",
                    "content": rendered_prompt.system_message
                    or "You are a database schema analyzer. Analyze the provided database table schema and provide semantic context.",
                },
                {"role": "user", "content": rendered_prompt.user_prompt},
            ],
            request_kwargs={},
            completeness_score=self._schema_completeness(table),
            coverage_score=self._schema_coverage(table),
            confidence_score=0.0,
            extra_metadata={
                "table_name": table.name,
                "column_count": len(table.columns or []),
            },
        )

    # ── Parse OpenAI response ──────────────────────────────────────────────

    def _parse_enrichment_response(
        self, table_id: int, database_id: int, response: str
    ) -> SemanticEnrichment:
        """
        Parse Azure OpenAI response into structured enrichment object.
        
        Expected response is a JSON object with semantic fields.
        """
        try:
            # Handle markdown JSON (sometimes the model wraps it)
            clean_response = response
            if "```json" in response:
                clean_response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                clean_response = response.split("```")[1].split("```")[0]

            data = json.loads(clean_response)

            return SemanticEnrichment(
                table_id=table_id,
                database_id=database_id,
                business_summary=data.get("business_summary", "").strip(),
                likely_usage=[u.strip() for u in data.get("likely_usage", [])],
                important_columns=[c.strip() for c in data.get("important_columns", [])],
                business_keywords=[k.strip() for k in data.get("business_keywords", [])],
                possible_questions=[q.strip() for q in data.get("possible_questions", [])],
                raw_response=response,
            )
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Azure OpenAI response: %s\nResponse: %s", e, response)
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")

    # ── Save enrichment to database ────────────────────────────────────────

    async def save_enrichment(
        self, db: AsyncSession, enrichment: SemanticEnrichment
    ) -> Any:
        """
        Save enrichment results to the schema_semantics table.
        
        Args:
            db: Async database session
            enrichment: SemanticEnrichment object to save
            
        Returns:
            The saved SchemaSemantic ORM object
        """
        # Import here to avoid circular imports
        from app.models.metadata import SchemaSemantic

        # Check if enrichment already exists for this table
        from sqlalchemy import select

        existing = await db.execute(
            select(SchemaSemantic).where(SchemaSemantic.table_id == enrichment.table_id)
        )
        semantic = existing.scalars().first()

        if semantic:
            # Update existing
            semantic.semantic_summary = enrichment.business_summary
            semantic.likely_usage = enrichment.likely_usage
            semantic.important_columns = enrichment.important_columns
            semantic.business_keywords = enrichment.business_keywords
            semantic.possible_questions = enrichment.possible_questions
            semantic.prompt_id = enrichment.prompt_id
            semantic.prompt_version = enrichment.prompt_version
            semantic.model_name = enrichment.model_name
            semantic.generated_at = enrichment.generated_at
            logger.info("Updated semantic enrichment for table %d", enrichment.table_id)
        else:
            # Create new
            semantic = SchemaSemantic(
                database_id=enrichment.database_id,
                table_id=enrichment.table_id,
                semantic_summary=enrichment.business_summary,
                prompt_id=enrichment.prompt_id,
                prompt_version=enrichment.prompt_version,
                model_name=enrichment.model_name,
                likely_usage=enrichment.likely_usage,
                important_columns=enrichment.important_columns,
                business_keywords=enrichment.business_keywords,
                possible_questions=enrichment.possible_questions,
                generated_at=enrichment.generated_at,
            )
            db.add(semantic)
            logger.info("Created new semantic enrichment for table %d", enrichment.table_id)

        await safe_flush(db)
        await db.refresh(semantic)
        return semantic
