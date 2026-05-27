"""
BaseConnector — abstract interface every database connector must implement.

All methods are async to ensure non-blocking execution in FastAPI.
Connectors must NEVER issue destructive queries (DROP, DELETE, TRUNCATE, etc.)
and must NEVER store credentials beyond the object lifetime.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data transfer objects returned by connectors ──────────────────────────────

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False
    is_indexed: bool = False
    default_value: Optional[str] = None
    max_length: Optional[int] = None
    ordinal_position: Optional[int] = None


@dataclass
class RelationshipInfo:
    column_name: str
    referenced_schema: Optional[str]
    referenced_table: str
    referenced_column: str
    constraint_name: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    table_type: str = "table"          # table | view | materialized_view
    row_count: Optional[int] = None
    columns: List[ColumnInfo] = field(default_factory=list)
    relationships: List[RelationshipInfo] = field(default_factory=list)


@dataclass
class SchemaInfo:
    name: str
    tables: List[TableInfo] = field(default_factory=list)


@dataclass
class DatabaseInfo:
    name: str
    schemas: List[SchemaInfo] = field(default_factory=list)


@dataclass
class ConnectionTestResult:
    success: bool
    message: str
    server_version: Optional[str] = None
    latency_ms: Optional[float] = None
    databases_accessible: Optional[int] = None


# ── Base connector ────────────────────────────────────────────────────────────

class BaseConnector(ABC):
    """
    Abstract connector — every supported database type must subclass this.

    Lifecycle:
      1. connector = SomeConnector(credentials)
      2. await connector.connect()          # establish connection
      3. info = await connector.introspect() # full schema discovery
      4. await connector.disconnect()       # always called in finally block
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        timeout: int = 30,
        ssl_enabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self._password = password       # kept private; never logged
        self.timeout = timeout
        self.ssl_enabled = ssl_enabled
        self._connected = False
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── Connection lifecycle ──────────────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the external database."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close and clean up the connection."""
        ...

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """
        Lightweight check — connect, ping, disconnect.
        Must be safe to call without a prior connect().
        """
        ...

    # ── Discovery ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_databases(self) -> List[str]:
        """Return names of all accessible databases on this server."""
        ...

    @abstractmethod
    async def get_schemas(self) -> List[str]:
        """Return schema names within the configured database."""
        ...

    @abstractmethod
    async def get_tables(self, schema: str) -> List[TableInfo]:
        """Return tables/views within the given schema (without column detail)."""
        ...

    @abstractmethod
    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """Return column metadata for a specific table."""
        ...

    @abstractmethod
    async def get_relationships(self, schema: str, table: str) -> List[RelationshipInfo]:
        """Return FK relationships for a specific table."""
        ...

    # ── Full introspection (orchestrates all get_* calls) ────────────────────

    async def introspect(self) -> List[SchemaInfo]:
        """
        Run a full schema introspection.
        Returns a list of SchemaInfo objects, each containing
        tables, columns, and relationships.

        Override for efficiency if the connector can batch queries.
        """
        schemas_names = await self.get_schemas()
        result: List[SchemaInfo] = []

        for schema_name in schemas_names:
            self.logger.debug("Introspecting schema: %s", schema_name)
            schema_info = SchemaInfo(name=schema_name)

            tables = await self.get_tables(schema=schema_name)
            for table in tables:
                try:
                    table.columns = await self.get_columns(schema=schema_name, table=table.name)
                    table.relationships = await self.get_relationships(
                        schema=schema_name, table=table.name
                    )
                except Exception as exc:
                    self.logger.warning(
                        "Failed to introspect %s.%s: %s", schema_name, table.name, exc
                    )
                schema_info.tables.append(table)

            result.append(schema_info)

        return result

    # ── Context manager support ───────────────────────────────────────────────

    async def __aenter__(self) -> "BaseConnector":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"host={self.host!r} db={self.database!r} connected={self._connected}>"
        )
