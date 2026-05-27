"""
PostgreSQL connector using asyncpg for async, non-blocking introspection.
Falls back to psycopg2 for synchronous test connections.
"""

import asyncio
import logging
import time
from typing import Any, List, Optional

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from app.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ConnectionTestResult,
    RelationshipInfo,
    SchemaInfo,
    TableInfo,
)
from app.utils import normalize_column_max_length

logger = logging.getLogger(__name__)

# Schemas we never introspect
EXCLUDED_SCHEMAS = frozenset(
    {"information_schema", "pg_catalog", "pg_toast", "pg_temp_1", "pg_toast_temp_1"}
)


class PostgresConnector(BaseConnector):
    """
    Read-only PostgreSQL connector.
    Uses asyncpg directly (not SQLAlchemy) for fine-grained control.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conn: Optional[Any] = None   # asyncpg.Connection

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for PostgreSQL connections. pip install asyncpg")
        try:
            self._conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.username,
                    password=self._password,
                    ssl=self.ssl_enabled or None,
                    command_timeout=self.timeout,
                ),
                timeout=self.timeout,
            )
            self._connected = True
            self.logger.info("Connected to PostgreSQL at %s:%s/%s", self.host, self.port, self.database)
        except Exception as exc:
            self._connected = False
            raise ConnectionError(f"PostgreSQL connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._conn:
            try:
                await self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
                self._connected = False

    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            async with self:                            # connect → introspect → disconnect
                row = await self._conn.fetchrow(
                    "SELECT version(), current_database()"
                )
                latency = (time.monotonic() - start) * 1000
                dbs = await self.get_databases()
                return ConnectionTestResult(
                    success=True,
                    message="Connection successful",
                    server_version=row["version"] if row else None,
                    latency_ms=round(latency, 2),
                    databases_accessible=len(dbs),
                )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                message=str(exc),
                latency_ms=round(latency, 2),
            )

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def get_databases(self) -> List[str]:
        rows = await self._conn.fetch(
            "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
        )
        return [r["datname"] for r in rows]

    async def get_schemas(self) -> List[str]:
        rows = await self._conn.fetch(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ($1, $2, $3, $4, $5)
              AND schema_name NOT LIKE 'pg_%'
            ORDER BY schema_name
            """,
            *list(EXCLUDED_SCHEMAS)[:5],
        )
        return [r["schema_name"] for r in rows]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        rows = await self._conn.fetch(
            """
            SELECT
                t.table_name,
                t.table_type,
                pg_stat_user_tables.n_live_tup AS row_count
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables
                ON pg_stat_user_tables.schemaname = t.table_schema
               AND pg_stat_user_tables.relname = t.table_name
            WHERE t.table_schema = $1
            ORDER BY t.table_name
            """,
            schema,
        )

        tables = []
        for r in rows:
            raw_type = r["table_type"]
            table_type = "view" if raw_type == "VIEW" else "table"
            tables.append(
                TableInfo(
                    name=r["table_name"],
                    table_type=table_type,
                    row_count=r["row_count"],
                )
            )
        return tables

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        rows = await self._conn.fetch(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.ordinal_position,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key,
                CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END AS is_foreign_key,
                CASE WHEN uq.column_name IS NOT NULL THEN true ELSE false END AS is_unique
            FROM information_schema.columns c
            -- Primary key
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = $1
                  AND tc.table_name = $2
            ) pk ON pk.column_name = c.column_name
            -- Foreign key
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = $1
                  AND tc.table_name = $2
            ) fk ON fk.column_name = c.column_name
            -- Unique
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'UNIQUE'
                  AND tc.table_schema = $1
                  AND tc.table_name = $2
            ) uq ON uq.column_name = c.column_name
            WHERE c.table_schema = $1 AND c.table_name = $2
            ORDER BY c.ordinal_position
            """,
            schema,
            table,
        )

        return [
            ColumnInfo(
                name=r["column_name"],
                data_type=r["data_type"],
                ordinal_position=r["ordinal_position"],
                is_nullable=r["is_nullable"] == "YES",
                is_primary_key=bool(r["is_primary_key"]),
                is_foreign_key=bool(r["is_foreign_key"]),
                is_unique=bool(r["is_unique"]),
                default_value=r["column_default"],
                max_length=normalize_column_max_length(
                    r["data_type"], r["character_maximum_length"]
                ),
            )
            for r in rows
        ]

    async def get_relationships(self, schema: str, table: str) -> List[RelationshipInfo]:
        rows = await self._conn.fetch(
            """
            SELECT
                kcu.column_name,
                ccu.table_schema  AS referenced_schema,
                ccu.table_name   AS referenced_table,
                ccu.column_name  AS referenced_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
               AND tc.table_schema = rc.constraint_schema
            JOIN information_schema.key_column_usage ccu
                ON rc.unique_constraint_name = ccu.constraint_name
               AND rc.unique_constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = $1
              AND tc.table_name = $2
            ORDER BY kcu.ordinal_position
            """,
            schema,
            table,
        )

        return [
            RelationshipInfo(
                column_name=r["column_name"],
                referenced_schema=r["referenced_schema"],
                referenced_table=r["referenced_table"],
                referenced_column=r["referenced_column"],
                constraint_name=r["constraint_name"],
            )
            for r in rows
        ]
