"""
SQL Server connector using aioodbc for async introspection.
"""

import asyncio
import logging
import time
from typing import Any, List, Optional

try:
    import aioodbc
    HAS_AIOODBC = True
except ImportError:
    HAS_AIOODBC = False

from app.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ConnectionTestResult,
    RelationshipInfo,
    TableInfo,
)
from app.utils import normalize_column_max_length

logger = logging.getLogger(__name__)

EXCLUDED_SCHEMAS = frozenset({"information_schema", "sys", "guest", "db_owner"})


class SQLServerConnector(BaseConnector):
    """Read-only SQL Server connector via ODBC."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._conn: Optional[Any] = None
        self._pool: Optional[Any] = None

    def _dsn(self) -> str:
        security = "Encrypt=yes;TrustServerCertificate=yes;" if self.ssl_enabled else ""
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self._password};"
            f"{security}"
            f"Connection Timeout={self.timeout};"
        )

    async def connect(self) -> None:
        if not HAS_AIOODBC:
            raise ImportError(
                "aioodbc is required for SQL Server connections. pip install aioodbc\n"
                "ODBC Driver 17 for SQL Server must also be installed on the host."
            )
        try:
            loop = asyncio.get_event_loop()
            self._conn = await aioodbc.connect(dsn=self._dsn(), loop=loop)
            self._connected = True
            self.logger.info(
                "Connected to SQL Server at %s:%s/%s", self.host, self.port, self.database
            )
        except Exception as exc:
            self._connected = False
            raise ConnectionError(f"SQL Server connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._conn:
            try:
                await self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
                self._connected = False

    async def _fetch(self, sql: str, *params: Any) -> List[dict]:
        async with self._conn.cursor() as cur:
            await cur.execute(sql, params or ())
            cols = [desc[0] for desc in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]

    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            async with self:
                rows = await self._fetch("SELECT @@VERSION AS ver")
                latency = (time.monotonic() - start) * 1000
                dbs = await self.get_databases()
                return ConnectionTestResult(
                    success=True,
                    message="Connection successful",
                    server_version=rows[0]["ver"][:100] if rows else None,
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
        rows = await self._fetch(
            "SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' ORDER BY name"
        )
        return [r["name"] for r in rows]

    async def get_schemas(self) -> List[str]:
        rows = await self._fetch(
            """
            SELECT s.name
            FROM sys.schemas s
            JOIN sys.database_principals p ON s.principal_id = p.principal_id
            WHERE s.name NOT IN ('information_schema','sys','guest','db_owner',
                                 'db_accessadmin','db_securityadmin','db_ddladmin',
                                 'db_backupoperator','db_datareader','db_datawriter',
                                 'db_denydatareader','db_denydatawriter')
            ORDER BY s.name
            """
        )
        return [r["name"] for r in rows]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        rows = await self._fetch(
            """
            SELECT t.name AS table_name,
                   CASE t.type WHEN 'U' THEN 'table' WHEN 'V' THEN 'view' ELSE 'table' END AS table_type,
                   p.rows AS row_count
            FROM sys.objects t
            LEFT JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
            WHERE t.type IN ('U','V')
              AND SCHEMA_NAME(t.schema_id) = ?
            ORDER BY t.name
            """,
            schema,
        )
        return [
            TableInfo(name=r["table_name"], table_type=r["table_type"], row_count=r["row_count"])
            for r in rows
        ]

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        rows = await self._fetch(
            """
            SELECT
                c.COLUMN_NAME, c.DATA_TYPE, c.ORDINAL_POSITION,
                c.IS_NULLABLE, c.COLUMN_DEFAULT, c.CHARACTER_MAXIMUM_LENGTH,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
                CASE WHEN fk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_foreign_key
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                  AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
            ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN (
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                  AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
            ) fk ON fk.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
            """,
            schema, table, schema, table, schema, table,
        )
        return [
            ColumnInfo(
                name=r["COLUMN_NAME"],
                data_type=r["DATA_TYPE"],
                ordinal_position=r["ORDINAL_POSITION"],
                is_nullable=r["IS_NULLABLE"] == "YES",
                is_primary_key=bool(r["is_primary_key"]),
                is_foreign_key=bool(r["is_foreign_key"]),
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
                COL_NAME(fc.parent_object_id, fc.parent_column_id) AS column_name,
                SCHEMA_NAME(reft.schema_id)                         AS referenced_schema,
                reft.name                                           AS referenced_table,
                COL_NAME(fc.referenced_object_id, fc.referenced_column_id) AS referenced_column,
                f.name AS constraint_name
            FROM sys.foreign_keys f
            JOIN sys.foreign_key_columns fc ON f.object_id = fc.constraint_object_id
            JOIN sys.tables reft ON f.referenced_object_id = reft.object_id
            WHERE OBJECT_SCHEMA_NAME(f.parent_object_id) = ?
              AND OBJECT_NAME(f.parent_object_id) = ?
            """,
            schema, table,
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
