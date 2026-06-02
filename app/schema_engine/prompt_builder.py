"""
PromptBuilder — Generate AI-ready schema prompts for LLM consumption.

Converts semantic enrichment into well-structured prompts that can be used
to provide context to LLMs for natural language SQL generation, schema exploration,
and other AI tasks.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.prompts import get_prompt_registry

from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseTable,
)

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Builds AI-ready schema prompts for LLM consumption.
    
    Usage:
        builder = PromptBuilder(db_session)
        prompt = await builder.build_database_context(database_id)
        print(prompt)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Database-level context prompt ──────────────────────────────────────

    async def build_database_context(self, database_id: int) -> str:
        """
        Build a comprehensive schema context prompt for an entire database.
        
        This prompt contains:
        - Database name and type
        - All tables and their descriptions
        - Key relationships (foreign keys)
        - Important metrics and fields
        - Semantic summaries for each table
        
        Args:
            database_id: Primary key of the connected database
            
        Returns:
            Formatted prompt string ready for LLM consumption
        """
        from sqlalchemy import select

        # Fetch database with all schemas and tables
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(
                    DatabaseSchema.tables
                ).selectinload(DatabaseTable.columns),
                selectinload(ConnectedDatabase.schemas).selectinload(
                    DatabaseSchema.tables
                ).selectinload(DatabaseTable.relationships_from),
            )
        )
        database = result.scalars().unique().first()

        if not database:
            raise ValueError(f"Database {database_id} not found")

        lines = [
            "=" * 80,
            f"DATABASE SCHEMA CONTEXT",
            "=" * 80,
            "",
            f"Database: {database.display_name or database.name}",
            f"Type: {database.db_type.value.upper()}",
            f"Status: {database.status.value}",
            "",
        ]

        # ── Collect all tables ─────────────────────────────────────────────
        all_tables = []
        for schema in database.schemas:
            for table in schema.tables:
                all_tables.append((schema.name, table))

        if not all_tables:
            lines.append("(No tables found)")
            return "\n".join(lines)

        context = await PromptStudioService(self.db)._build_context(database_id)
        return get_prompt_registry().render_prompt(
            "database_context",
            context,
            category="system",
        ).user_prompt

        lines.append(f"Tables: {len(all_tables)}")
        lines.append("")

        # ── Build table summaries ──────────────────────────────────────────
        for schema_name, table in all_tables:
            lines.extend(self._format_table_section(schema_name, table))
            lines.append("")

        # ── Build relationship summary ─────────────────────────────────────
        relationships = self._extract_relationships(all_tables)
        if relationships:
            lines.append("KEY RELATIONSHIPS")
            lines.append("-" * 40)
            for rel in relationships:
                lines.append(rel)
            lines.append("")

        # ── Close ──────────────────────────────────────────────────────────
        lines.append("=" * 80)
        lines.append("Use this context to understand the database structure and relationships.")
        lines.append("=" * 80)

        return "\n".join(lines)

    # ── Table-level context prompt ─────────────────────────────────────────

    async def build_table_context(self, table_id: int) -> str:
        """
        Build a focused schema context prompt for a single table.
        
        Args:
            table_id: Primary key of the table
            
        Returns:
            Formatted prompt string
        """
        table = await self._fetch_table_with_context(table_id)
        if not table:
            raise ValueError(f"Table {table_id} not found")

        return self._build_table_prompt_text(table)

    # ── Helper: format table section ───────────────────────────────────────

    def _format_table_section(self, schema_name: str, table: DatabaseTable) -> list[str]:
        """Format a single table into a prompt section."""
        lines = [
            f"TABLE: {schema_name}.{table.name}",
            "-" * 40,
        ]

        if table.description:
            lines.append(f"Description: {table.description}")

        if table.table_type.value != "table":
            lines.append(f"Type: {table.table_type.value}")

        if table.row_count is not None:
            lines.append(f"Rows: {table.row_count:,}")

        lines.append("")
        lines.append("Columns:")

        for col in sorted(table.columns, key=lambda c: c.ordinal_position or 0):
            col_str = f"  • {col.name}: {col.data_type}"

            constraints = []
            if col.is_primary_key:
                constraints.append("PRIMARY KEY")
            if col.is_foreign_key:
                constraints.append("FOREIGN KEY")
            if col.is_unique:
                constraints.append("UNIQUE")
            if not col.is_nullable:
                constraints.append("NOT NULL")

            if constraints:
                col_str += f" [{', '.join(constraints)}]"

            if col.description:
                col_str += f" — {col.description}"

            lines.append(col_str)

        # ── Outgoing relationships ─────────────────────────────────────────
        if table.relationships_from:
            lines.append("")
            lines.append("Relationships:")
            for rel in table.relationships_from:
                rel_str = (
                    f"  • {rel.column_name} → "
                    f"{rel.referenced_table_name}.{rel.referenced_column_name}"
                )
                lines.append(rel_str)

        return lines

    # ── Helper: extract relationships ──────────────────────────────────────

    def _extract_relationships(self, tables: list[tuple[str, DatabaseTable]]) -> list[str]:
        """Extract and format all foreign key relationships."""
        relationships = []
        seen = set()

        for schema_name, table in tables:
            for rel in table.relationships_from:
                # Avoid duplicates
                rel_key = (rel.column_name, rel.referenced_table_name, rel.referenced_column_name)
                if rel_key in seen:
                    continue
                seen.add(rel_key)

                rel_str = (
                    f"{schema_name}.{table.name}.{rel.column_name} → "
                    f"{rel.referenced_table_name}.{rel.referenced_column_name}"
                )
                relationships.append(rel_str)

        return sorted(relationships)

    # ── Helper: fetch table with context ───────────────────────────────────

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

    # ── Helper: build full table prompt ────────────────────────────────────

    def _build_table_prompt_text(self, table: DatabaseTable) -> str:
        """Build a complete prompt for a single table."""
        lines = [
            "=" * 80,
            "TABLE SCHEMA",
            "=" * 80,
            "",
        ]

        lines.extend(self._format_table_section(table.schema.name, table))

        lines.extend(
            [
                "",
                "=" * 80,
                "Use this table schema for understanding the data structure.",
                "=" * 80,
            ]
        )

        return "\n".join(lines)

    # ── Generate semantic context prompt ───────────────────────────────────

    async def build_semantic_context(self, database_id: int) -> str:
        """
        Build a prompt that includes semantic enrichment data.
        
        Combines raw schema context with AI-generated business summaries
        and usage patterns for richer LLM context.
        
        Args:
            database_id: Primary key of the connected database
            
        Returns:
            Formatted prompt with semantic enrichment
        """
        from sqlalchemy import select

        from app.models.metadata import SchemaSemantic

        # Fetch database with schemas and tables
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(
                    DatabaseSchema.tables
                ).selectinload(DatabaseTable.columns),
            )
        )
        database = result.scalars().unique().first()

        if not database:
            raise ValueError(f"Database {database_id} not found")

        # Fetch semantic enrichments for all tables
        semantic_result = await self.db.execute(
            select(SchemaSemantic).where(SchemaSemantic.database_id == database_id)
        )
        semantics = {s.table_id: s for s in semantic_result.scalars().all()}

        context = await PromptStudioService(self.db)._build_context(database_id)
        return get_prompt_registry().render_prompt(
            "rag_context",
            context,
            category="system",
        ).user_prompt

        lines = [
            "=" * 80,
            "DATABASE SCHEMA + SEMANTIC CONTEXT",
            "=" * 80,
            "",
            f"Database: {database.display_name or database.name}",
            f"Type: {database.db_type.value.upper()}",
            "",
        ]

        # ── Build table sections with semantic data ────────────────────────
        for schema in database.schemas:
            for table in schema.tables:
                lines.extend(self._format_table_section(schema.name, table))

                # Add semantic enrichment if available
                if table.id in semantics:
                    semantic = semantics[table.id]
                    lines.append("")
                    lines.append("SEMANTIC CONTEXT:")
                    lines.append(f"  Business Summary: {semantic.semantic_summary}")

                    if semantic.likely_usage:
                        lines.append(f"  Likely Usage: {', '.join(semantic.likely_usage)}")

                    if semantic.important_columns:
                        lines.append(f"  Key Columns: {', '.join(semantic.important_columns)}")

                    if semantic.business_keywords:
                        lines.append(f"  Keywords: {', '.join(semantic.business_keywords)}")

                    if semantic.possible_questions:
                        lines.append("  Possible Questions:")
                        for q in semantic.possible_questions[:5]:  # Show top 5
                            lines.append(f"    - {q}")

                lines.append("")

        lines.append("=" * 80)
        lines.append("Use this context for schema understanding and data exploration.")
        lines.append("=" * 80)

        return "\n".join(lines)
