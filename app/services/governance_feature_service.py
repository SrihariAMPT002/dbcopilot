"""Feature assembly for governance reasoning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.metadata import (
    ColumnStatistics,
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
)
from app.services.pii_rule_service import PIIRuleMatch, PIIRuleService


@dataclass
class GovernanceColumnFeature:
    column_id: int
    column_name: str
    data_type: str
    nullable: bool
    primary_key: bool
    foreign_key: bool
    neighbor_context: str
    rule_matches: list[dict[str, Any]]
    sample_patterns: list[str]
    statistics: dict[str, Any]
    evidence: list[dict[str, Any]]


class GovernanceFeatureService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rule_service = PIIRuleService()

    async def fetch_table(self, table_id: int) -> tuple[ConnectedDatabase, DatabaseSchema, DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable)
            .options(
                selectinload(DatabaseTable.schema).selectinload(DatabaseSchema.connected_database),
                selectinload(DatabaseTable.columns),
            )
            .where(DatabaseTable.id == table_id)
        )
        table = result.scalar_one_or_none()
        if table is None:
            raise ValueError(f"Table {table_id} not found")
        return table.schema.connected_database, table.schema, table

    async def fetch_column_statistics(self, column_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not column_ids:
            return {}
        result = await self.db.execute(
            select(ColumnStatistics).where(ColumnStatistics.column_id.in_(column_ids))
        )
        stats: dict[int, dict[str, Any]] = {}
        for row in result.scalars().all():
            try:
                stats[row.column_id] = json.loads(row.stats_json or "{}")
            except Exception:
                stats[row.column_id] = {}
        return stats

    def build_feature(
        self,
        *,
        database: ConnectedDatabase,
        schema: DatabaseSchema,
        table: DatabaseTable,
        column: DatabaseColumn,
        statistics: dict[str, Any] | None = None,
        neighbors: list[DatabaseColumn] | None = None,
    ) -> GovernanceColumnFeature:
        neighbors = neighbors or []
        neighbor_context = ", ".join(
            f"{neighbor.name}:{neighbor.data_type}" for neighbor in neighbors if neighbor.id != column.id
        )
        table_context = f"{database.display_name or database.name} {schema.name} {table.name} {table.description or ''}"
        rule_matches = [match.to_dict() for match in self.rule_service.match_column(
            column_name=column.name,
            data_type=column.data_type,
            table_context=table_context,
            neighbor_context=neighbor_context,
        )]
        sample_patterns = [match["matched_value"] for match in rule_matches if match.get("matched_value")]
        evidence = [
            {
                "source": "metadata",
                "column_name": column.name,
                "data_type": column.data_type,
                "nullable": bool(column.is_nullable),
                "primary_key": bool(column.is_primary_key),
                "foreign_key": bool(column.is_foreign_key),
            }
        ]
        if statistics:
            evidence.append({"source": "statistics", **statistics})
        if neighbor_context:
            evidence.append({"source": "neighbor_context", "value": neighbor_context})
        return GovernanceColumnFeature(
            column_id=column.id,
            column_name=column.name,
            data_type=column.data_type,
            nullable=bool(column.is_nullable),
            primary_key=bool(column.is_primary_key),
            foreign_key=bool(column.is_foreign_key),
            neighbor_context=neighbor_context,
            rule_matches=rule_matches,
            sample_patterns=sample_patterns,
            statistics=statistics or {},
            evidence=evidence,
        )

    async def upsert_column_statistics(
        self,
        *,
        database: ConnectedDatabase,
        schema: DatabaseSchema,
        table: DatabaseTable,
        column: DatabaseColumn,
        feature: GovernanceColumnFeature,
    ) -> ColumnStatistics:
        result = await self.db.execute(
            select(ColumnStatistics).where(ColumnStatistics.column_id == column.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ColumnStatistics(
                database_id=database.id,
                table_id=table.id,
                column_id=column.id,
                column_name=column.name,
                data_type=column.data_type,
            )
            self.db.add(row)
        row.database_id = database.id
        row.table_id = table.id
        row.column_id = column.id
        row.column_name = column.name
        row.data_type = column.data_type
        row.stats_json = json.dumps(
            {
                "nullable": feature.nullable,
                "primary_key": feature.primary_key,
                "foreign_key": feature.foreign_key,
                "neighbor_context": feature.neighbor_context,
                "rule_matches": feature.rule_matches,
                "sample_patterns": feature.sample_patterns,
                "evidence": feature.evidence,
                "table_name": table.name,
                "schema_name": schema.name,
            }
        )
        await self.db.flush()
        return row
