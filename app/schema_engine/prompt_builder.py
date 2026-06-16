"""PromptBuilder - generate AI-ready schema prompts for LLM consumption."""

from __future__ import annotations

from typing import Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.prompts import get_prompt_registry
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable
from app.services.prompt_studio_service import PromptStudioService

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds AI-ready schema prompts for LLM consumption."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_database_context(self, database_id: int) -> str:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.columns),
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.relationships_from),
            )
        )
        database = result.scalars().unique().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")

        context = await PromptStudioService(self.db)._build_context(database_id)
        return get_prompt_registry().render_prompt("database_context", context, category="system").user_prompt

    async def build_table_context(self, table_id: int) -> str:
        table = await self._fetch_table_with_context(table_id)
        if not table:
            raise ValueError(f"Table {table_id} not found")
        return self._build_table_prompt_text(table)

    async def build_semantic_context(self, database_id: int) -> str:
        result = await self.db.execute(
            select(ConnectedDatabase)
            .where(ConnectedDatabase.id == database_id)
            .options(
                selectinload(ConnectedDatabase.schemas).selectinload(DatabaseSchema.tables).selectinload(DatabaseTable.columns),
            )
        )
        database = result.scalars().unique().first()
        if not database:
            raise ValueError(f"Database {database_id} not found")

        context = await PromptStudioService(self.db)._build_context(database_id)
        return get_prompt_registry().render_prompt("rag_context", context, category="system").user_prompt

    def _build_table_prompt_text(self, table: DatabaseTable) -> str:
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

    def _format_table_section(self, schema_name: str, table: DatabaseTable) -> list[str]:
        lines = [f"TABLE: {schema_name}.{table.name}", "-" * 40]
        if table.description:
            lines.append(f"Description: {table.description}")
        if table.table_type.value != "table":
            lines.append(f"Type: {table.table_type.value}")
        if table.row_count is not None:
            lines.append(f"Rows: {table.row_count:,}")
        lines.append("")
        lines.append("Columns:")
        for col in sorted(table.columns or [], key=lambda c: c.ordinal_position or 0):
            col_str = f"  * {col.name}: {col.data_type}"
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
                col_str += f" - {col.description}"
            lines.append(col_str)
        if table.relationships_from:
            lines.append("")
            lines.append("Relationships:")
            for rel in table.relationships_from or []:
                lines.append(f"  * {rel.column_name} -> {rel.referenced_table_name}.{rel.referenced_column_name}")
        return lines

    async def _fetch_table_with_context(self, table_id: int) -> Optional[DatabaseTable]:
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
