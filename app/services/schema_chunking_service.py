"""Hierarchical schema chunking for large-database AI payloads.

This helper compresses database metadata into progressively smaller
database, schema, table, and column summaries so AI prompts can stay within
reasonable token budgets even for large catalogs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.exc import InvalidRequestError

from app.models.metadata import ConnectedDatabase, DatabaseColumn, DatabaseSchema, DatabaseTable


@dataclass
class ColumnChunkSummary:
    column_name: str
    data_type: str | None
    nullable: bool
    primary_key: bool
    foreign_key: bool
    unique: bool
    indexed: bool
    description: str | None = None


@dataclass
class TableChunkSummary:
    schema_name: str
    table_name: str
    table_type: str
    description: str | None
    column_count: int
    relationship_count: int
    pii_column_count: int
    has_primary_key: bool
    has_foreign_keys: bool
    columns: list[ColumnChunkSummary]


@dataclass
class SchemaChunkSummary:
    schema_name: str
    table_count: int
    relationship_count: int
    tables: list[TableChunkSummary]


class SchemaChunkingService:
    """Compress database metadata into hierarchical summaries."""

    def __init__(self, max_schemas: int = 8, max_tables_per_schema: int = 8, max_columns_per_table: int = 12) -> None:
        self.max_schemas = max_schemas
        self.max_tables_per_schema = max_tables_per_schema
        self.max_columns_per_table = max_columns_per_table

    @staticmethod
    def _table_type(table: DatabaseTable) -> str:
        value = getattr(table.table_type, "value", table.table_type)
        return str(value)

    @staticmethod
    def _safe_text(text: str | None) -> str | None:
        if not text:
            return None
        stripped = text.strip()
        return stripped or None

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        try:
            return list(value)
        except TypeError:
            return []

    def _column_summary(self, column: DatabaseColumn) -> ColumnChunkSummary:
        return ColumnChunkSummary(
            column_name=column.name,
            data_type=getattr(column, "data_type", None),
            nullable=bool(getattr(column, "is_nullable", None)),
            primary_key=bool(getattr(column, "is_primary_key", None)),
            foreign_key=bool(getattr(column, "is_foreign_key", None)),
            unique=bool(getattr(column, "is_unique", None)),
            indexed=bool(getattr(column, "is_indexed", None)),
            description=self._safe_text(getattr(column, "description", None)),
        )

    def _table_summary(self, table: DatabaseTable, *, pii_column_names: set[str] | None = None) -> TableChunkSummary:
        try:
            columns = sorted(self._safe_list(getattr(table, "columns", None)), key=lambda column: getattr(column, "ordinal_position", 0) or 0)
        except InvalidRequestError:
            columns = []
        limited_columns = columns[: self.max_columns_per_table]
        pii_names = pii_column_names or set()
        return TableChunkSummary(
            schema_name=table.schema.name,
            table_name=table.name,
            table_type=self._table_type(table),
            description=self._safe_text(getattr(table, "description", None)),
            column_count=len(columns),
            relationship_count=len(self._safe_list(getattr(table, "relationships_from", None))),
            pii_column_count=sum(1 for column in columns if column.name in pii_names),
            has_primary_key=any(bool(getattr(column, "is_primary_key", None)) for column in columns),
            has_foreign_keys=any(bool(getattr(column, "is_foreign_key", None)) for column in columns),
            columns=[self._column_summary(column) for column in limited_columns],
        )

    def _schema_summary(self, schema: DatabaseSchema, *, pii_map: dict[int, Any] | None = None) -> SchemaChunkSummary:
        try:
            tables = sorted(self._safe_list(getattr(schema, "tables", None)), key=lambda table: table.name)
        except InvalidRequestError:
            tables = []
        limited_tables = tables[: self.max_tables_per_schema]
        table_summaries = []
        relationship_count = 0
        for table in limited_tables:
            pii_column_names = {
                column.name
                for column in self._safe_list(getattr(table, "columns", None))
                if pii_map and getattr(pii_map.get(column.id), "is_pii", False)
            }
            table_summary = self._table_summary(table, pii_column_names=pii_column_names)
            relationship_count += table_summary.relationship_count
            table_summaries.append(table_summary)
        return SchemaChunkSummary(
            schema_name=schema.name,
            table_count=len(tables),
            relationship_count=relationship_count,
            tables=table_summaries,
        )

    def _database_totals(self, database: ConnectedDatabase) -> dict[str, int]:
        try:
            schemas = self._safe_list(getattr(database, "schemas", None))
        except InvalidRequestError:
            schemas = []
        tables = [table for schema in schemas for table in self._safe_list(getattr(schema, "tables", None))]
        columns = [column for table in tables for column in self._safe_list(getattr(table, "columns", None))]
        relationships = [rel for table in tables for rel in self._safe_list(getattr(table, "relationships_from", None))]
        return {
            "schema_count": len(schemas),
            "table_count": len(tables),
            "column_count": len(columns),
            "relationship_count": len(relationships),
        }

    def build(self, database: ConnectedDatabase, *, pii_map: dict[int, Any] | None = None) -> dict[str, Any]:
        """Return a hierarchical, token-bounded summary of the database."""
        try:
            schemas = sorted(self._safe_list(getattr(database, "schemas", None)), key=lambda schema: schema.name)
        except InvalidRequestError:
            schemas = []
        limited_schemas = schemas[: self.max_schemas]
        schema_summaries = [self._schema_summary(schema, pii_map=pii_map) for schema in limited_schemas]
        totals = self._database_totals(database)
        return {
            "database_id": database.id,
            "database_name": database.display_name or database.name,
            "database_type": getattr(database.db_type, "value", database.db_type),
            "totals": totals,
            "schema_summaries": [
                {
                    "schema_name": schema.schema_name,
                    "table_count": schema.table_count,
                    "relationship_count": schema.relationship_count,
                    "tables": [
                        {
                            "schema_name": table.schema_name,
                            "table_name": table.table_name,
                            "table_type": table.table_type,
                            "description": table.description,
                            "column_count": table.column_count,
                            "relationship_count": table.relationship_count,
                            "pii_column_count": table.pii_column_count,
                            "has_primary_key": table.has_primary_key,
                            "has_foreign_keys": table.has_foreign_keys,
                            "columns": [column.__dict__ for column in table.columns],
                        }
                        for table in schema.tables
                    ],
                }
                for schema in schema_summaries
            ],
            "schema_chunk_count": len(schema_summaries),
            "truncated": len(schemas) > self.max_schemas,
        }

    def table_summaries(self, schema: DatabaseSchema, *, pii_map: dict[int, Any] | None = None) -> list[dict[str, Any]]:
        return [
            {
                "schema_name": summary.schema_name,
                "table_name": summary.table_name,
                "table_type": summary.table_type,
                "description": summary.description,
                "column_count": summary.column_count,
                "relationship_count": summary.relationship_count,
                "pii_column_count": summary.pii_column_count,
                "has_primary_key": summary.has_primary_key,
                "has_foreign_keys": summary.has_foreign_keys,
                "columns": [column.__dict__ for column in summary.columns],
            }
            for summary in [
                self._table_summary(
                    table,
                    pii_column_names={
                        column.name
                        for column in self._safe_list(getattr(table, "columns", None))
                        if pii_map and getattr(pii_map.get(column.id), "is_pii", False)
                    },
                )
                for table in sorted(self._safe_list(getattr(schema, "tables", None)), key=lambda table: table.name)[: self.max_tables_per_schema]
            ]
        ]

    @classmethod
    def safe_summary_list(cls, items: Iterable[Any]) -> list[Any]:
        return cls._safe_list(items)  # type: ignore[misc]
