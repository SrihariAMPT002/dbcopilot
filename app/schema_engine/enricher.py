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
from app.schema_engine.metrics import MetricsEngine
from app.utils import safe_flush

logger = logging.getLogger(__name__)

# ── Azure OpenAI Client (lazy initialization) ────────────────────────────────

_openai_client = None


def get_openai_client():
    """Lazy-load OpenAI client with Azure configuration."""
    global _openai_client
    if _openai_client is None:
        if not settings.azure_openai_endpoint or not settings.azure_openai_key:
            raise ValueError(
                "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY"
            )
        try:
            from openai import AzureOpenAI
            
            _openai_client = AzureOpenAI(
                api_key=settings.azure_openai_key,
                api_version=settings.azure_openai_api_version,
                azure_endpoint=settings.azure_openai_endpoint,
            )
        except ImportError:
            raise ImportError(
                "openai package not installed. Install with: pip install openai"
            )
    return _openai_client


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
    ):
        self.table_id = table_id
        self.database_id = database_id
        self.business_summary = business_summary
        self.likely_usage = likely_usage
        self.important_columns = important_columns
        self.business_keywords = business_keywords
        self.possible_questions = possible_questions
        self.raw_response = raw_response
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
            response = await self._call_azure_openai(context_doc)
            self.metrics.record_openai_call(time.time() - start_time)
        except Exception as e:
            logger.error("Azure OpenAI call failed: %s", e, exc_info=True)
            self.metrics.record_openai_error()
            raise

        # Parse response
        enrichment = self._parse_enrichment_response(table_id, table.schema.connected_db_id, response)

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
        for col in sorted(table.columns, key=lambda c: c.ordinal_position or 0):
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

    # ── Call Azure OpenAI ──────────────────────────────────────────────────

    async def _call_azure_openai(self, context_doc: str) -> str:
        """
        Call Azure OpenAI GPT-4o to generate semantic enrichment.
        
        Uses a system prompt to guide the model toward specific outputs.
        """
        client = get_openai_client()

        system_prompt = """You are a database schema analyzer. Analyze the provided database table schema and provide:

1. A 2-3 sentence business summary of what this table likely contains
2. List of 3-5 likely usage patterns (e.g., "sales analytics", "customer reporting")
3. List of 3-5 key/important column names
4. List of 5-10 business keywords related to this table
5. List of 5-10 possible analytics questions that could be answered with this data

Return ONLY a valid JSON object (no markdown, no extra text) with these fields:
{
  "business_summary": "string",
  "likely_usage": ["string", ...],
  "important_columns": ["string", ...],
  "business_keywords": ["string", ...],
  "possible_questions": ["string", ...]
}"""

        user_message = f"Analyze this database table:\n\n{context_doc}"

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,  # Low temperature for consistency
                max_tokens=1000,
            ),
        )

        return response.choices[0].message.content

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
            semantic.generated_at = enrichment.generated_at
            logger.info("Updated semantic enrichment for table %d", enrichment.table_id)
        else:
            # Create new
            semantic = SchemaSemantic(
                database_id=enrichment.database_id,
                table_id=enrichment.table_id,
                semantic_summary=enrichment.business_summary,
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
