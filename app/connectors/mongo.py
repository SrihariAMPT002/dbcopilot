"""
MongoDB connector using motor (async MongoDB driver).

MongoDB has no schema in the SQL sense, so we:
  - Treat each collection as a "table"
  - Sample documents to infer field types
  - Report one pseudo-schema named after the database
"""

import logging
import time
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional

try:
    import motor.motor_asyncio as motor
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False

from app.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ConnectionTestResult,
    RelationshipInfo,
    TableInfo,
)

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 20  # documents to sample per collection for type inference


def _infer_type(value: Any) -> str:
    """Map a Python value to a MongoDB-style type string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    type_name = type(value).__name__
    return type_name  # ObjectId, datetime, etc.


def _infer_schema(docs: List[dict]) -> Dict[str, str]:
    """Merge field types across sampled documents."""
    field_types: Dict[str, str] = {}
    for doc in docs:
        for key, value in doc.items():
            if key not in field_types:
                field_types[key] = _infer_type(value)
            # If type differs, mark as mixed
            elif field_types[key] != _infer_type(value):
                field_types[key] = "mixed"
    return field_types


class MongoConnector(BaseConnector):
    """Read-only MongoDB connector via motor."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: Optional[Any] = None

    def _build_uri(self) -> str:
        username = quote_plus(self.username)
        password = quote_plus(self._password)
        tls_params = "&tls=true" if self.ssl_enabled else ""
        return (
            f"mongodb://{username}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?serverSelectionTimeoutMS={self.timeout * 1000}"
            f"&connectTimeoutMS={self.timeout * 1000}"
            f"&socketTimeoutMS={self.timeout * 1000}"
            f"{tls_params}"
        )

    async def connect(self) -> None:
        if not HAS_MOTOR:
            raise ImportError(
                "motor is required for MongoDB connections. pip install motor"
            )
        try:
            self._client = motor.AsyncIOMotorClient(self._build_uri())
            # Force a real connection attempt
            await self._client.admin.command("ping")
            self._connected = True
            self.logger.info(
                "Connected to MongoDB at %s:%s/%s", self.host, self.port, self.database
            )
        except Exception as exc:
            self._connected = False
            raise ConnectionError(f"MongoDB connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            finally:
                self._client = None
                self._connected = False

    async def test_connection(self) -> ConnectionTestResult:
        start = time.monotonic()
        try:
            async with self:
                info = await self._client.admin.command("serverStatus")
                version = info.get("version", "unknown")
                latency = (time.monotonic() - start) * 1000
                dbs = await self.get_databases()
                return ConnectionTestResult(
                    success=True,
                    message="Connection successful",
                    server_version=f"MongoDB {version}",
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
        return await self._client.list_database_names()

    async def get_schemas(self) -> List[str]:
        # MongoDB schema = database name (one schema per database)
        return [self.database]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        db = self._client[schema]
        collection_names = await db.list_collection_names()
        tables = []
        for name in sorted(collection_names):
            try:
                count = await db[name].estimated_document_count()
            except Exception:
                count = None
            tables.append(TableInfo(name=name, table_type="table", row_count=count))
        return tables

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        db = self._client[schema]
        coll = db[table]
        # Sample documents to infer field types
        docs = await coll.find({}, {"_id": 1}).to_list(length=SAMPLE_SIZE)
        # Re-fetch without projection limit for type inference
        docs = await coll.find({}).to_list(length=SAMPLE_SIZE)
        field_types = _infer_schema(docs)

        columns = []
        for idx, (field_name, field_type) in enumerate(sorted(field_types.items()), start=1):
            columns.append(
                ColumnInfo(
                    name=field_name,
                    data_type=field_type,
                    ordinal_position=idx,
                    is_nullable=True,  # MongoDB fields are always optional
                    is_primary_key=(field_name == "_id"),
                )
            )
        return columns

    async def get_relationships(self, schema: str, table: str) -> List[RelationshipInfo]:
        # MongoDB has no native FK constraints
        return []
