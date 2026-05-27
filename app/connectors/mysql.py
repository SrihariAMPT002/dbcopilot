"""
MySQL connector using aiomysql for async introspection.
"""

import asyncio
import logging
import time
import ssl as ssl_module
from typing import Any, List, Optional

try:
    import aiomysql
    HAS_AIOMYSQL = True
except ImportError:
    HAS_AIOMYSQL = False

from app.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ConnectionTestResult,
    RelationshipInfo,
    TableInfo,
)
from app.utils import normalize_column_max_length

logger = logging.getLogger(__name__)

EXCLUDED_SCHEMAS = frozenset(
    {"information_schema", "performance_schema", "mysql", "sys"}
)


class MySQLConnector(BaseConnector):
    """Read-only MySQL / MariaDB connector."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conn: Optional[Any] = None   # aiomysql.Connection

    async def connect(self) -> None:
        if not HAS_AIOMYSQL:
            raise ImportError("aiomysql is required for MySQL connections. pip install aiomysql")
        try:
            self._conn = await asyncio.wait_for(
                aiomysql.connect(
                    host=self.host,
                    port=self.port,
                    db=self.database,
                    user=self.username,
                    password=self._password,
                    ssl=ssl_module.create_default_context() if self.ssl_enabled else None,
                    connect_timeout=self.timeout,
                    charset="utf8mb4",
                    autocommit=True,
                ),
                timeout=self.timeout,
            )
            self._connected = True
            self.logger.info("Connected to MySQL at %s:%s/%s", self.host, self.port, self.database)
        except Exception as exc:
            self._connected = False
            raise ConnectionError(f"MySQL connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
                self._connected = False

    async def _fetch(self, sql: str, *args: Any) -> List[dict]:
        async with self._conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args or None)
            return await cur.fetchall()

    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            async with self:
                rows = await self._fetch("SELECT VERSION() AS ver")
                latency = (time.monotonic() - start) * 1000
                dbs = await self.get_databases()
                return ConnectionTestResult(
                    success=True,
                    message="Connection successful",
                    server_version=rows[0]["ver"] if rows else None,
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

    async def get_databases(self) -> List[str]:
        rows = await self._fetch("SHOW DATABASES")
        return [
            r["Database"]
            for r in rows
            if r["Database"] not in EXCLUDED_SCHEMAS
        ]

    async def get_schemas(self) -> List[str]:
        # MySQL: schema == database
        return [self.database]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        rows = await self._fetch(
            """
            SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
            """,
            schema,
        )
        tables = []
        for r in rows:
            raw_type = r["TABLE_TYPE"]
            ttype = "view" if "VIEW" in raw_type.upper() else "table"
            tables.append(
                TableInfo(
                    name=r["TABLE_NAME"],
                    table_type=ttype,
                    row_count=r["TABLE_ROWS"],
                )
            )
        return tables

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        rows = await self._fetch(
            """
            SELECT
                COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION,
                IS_NULLABLE, COLUMN_DEFAULT, CHARACTER_MAXIMUM_LENGTH,
                COLUMN_KEY, EXTRA
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            schema,
            table,
        )
        return [
            ColumnInfo(
                name=r["COLUMN_NAME"],
                data_type=r["DATA_TYPE"],
                ordinal_position=r["ORDINAL_POSITION"],
                is_nullable=r["IS_NULLABLE"] == "YES",
                is_primary_key=r["COLUMN_KEY"] == "PRI",
                is_foreign_key=r["COLUMN_KEY"] == "MUL",
                is_unique=r["COLUMN_KEY"] == "UNI",
                default_value=r["COLUMN_DEFAULT"],
                max_length=normalize_column_max_length(
                    r["DATA_TYPE"], r["CHARACTER_MAXIMUM_LENGTH"]
                ),
            )
            for r in rows
        ]

    async def get_relationships(self, schema: str, table: str) -> List[RelationshipInfo]:
        rows = await self._fetch(
            """
            SELECT
                COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
                REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME,
                CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            schema,
            table,
        )
        return [
            RelationshipInfo(
                column_name=r["COLUMN_NAME"],
                referenced_schema=r["REFERENCED_TABLE_SCHEMA"],
                referenced_table=r["REFERENCED_TABLE_NAME"],
                referenced_column=r["REFERENCED_COLUMN_NAME"],
                constraint_name=r["CONSTRAINT_NAME"],
            )
            for r in rows
        ]
