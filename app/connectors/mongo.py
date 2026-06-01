"""
MongoDB connector using motor (async MongoDB driver).

MongoDB has no schema in the SQL sense, so we:
  - Treat each collection as a "table"
  - Sample documents to infer field types
  - Report one pseudo-schema named after the database
"""

import logging
import time
from collections import defaultdict
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
from app.connectors.base_nosql import BaseNoSQLConnector, InferredFieldProfile

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


class MongoConnector(BaseNoSQLConnector):
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
        docs = await coll.find({}).limit(SAMPLE_SIZE).to_list(length=SAMPLE_SIZE)
        profiles = self.build_field_profiles(docs, _infer_type)

        columns = []
        for idx, profile in enumerate(profiles, start=1):
            # Store NoSQL hints in existing SQL-shaped columns without schema changes:
            # type includes nested/array/occurrence metadata for compatibility.
            type_label = profile.inferred_data_type
            if profile.is_array:
                type_label = f"array<{type_label}>"
            type_label = f"{type_label} [occ:{profile.occurrence_percentage:.1f}% depth:{profile.nested_depth}]"
            columns.append(
                ColumnInfo(
                    name=profile.field_path,
                    data_type=type_label,
                    ordinal_position=idx,
                    is_nullable=True,  # MongoDB fields are always optional
                    is_primary_key=(profile.field_path == "_id"),
                )
            )
        return columns

    async def get_relationships(self, schema: str, table: str) -> List[RelationshipInfo]:
        db = self._client[schema]
        coll = db[table]
        docs = await coll.find({}).limit(SAMPLE_SIZE).to_list(length=SAMPLE_SIZE)
        relationships: list[RelationshipInfo] = []
        collection_names = set(await db.list_collection_names())
        seen: set[tuple[str, str]] = set()

        for profile in self.build_field_profiles(docs, _infer_type):
            field = profile.field_path
            normalized = field.replace("[]", "")
            if normalized.endswith("_id") and normalized != "_id":
                candidate = normalized[:-3]
                # very simple pluralization heuristic
                targets = [candidate, f"{candidate}s", f"{candidate}es"]
                target = next((t for t in targets if t in collection_names), None)
                if target and (field, target) not in seen:
                    confidence = max(0.35, min(0.95, profile.occurrence_percentage / 100.0))
                    relationships.append(
                        RelationshipInfo(
                            column_name=field,
                            referenced_schema=schema,
                            referenced_table=target,
                            referenced_column="_id",
                            constraint_name=f"inferred_ref:{confidence:.2f}",
                        )
                    )
                    seen.add((field, target))
        return relationships

    async def infer_collection_schema(self, schema: str, collection: str, sample_size: int = SAMPLE_SIZE) -> dict[str, Any]:
        db = self._client[schema]
        coll = db[collection]
        docs = await coll.find({}).limit(sample_size).to_list(length=sample_size)
        profiles = self.build_field_profiles(docs, _infer_type)

        # basic relationship inference summary
        rels = await self.get_relationships(schema, collection)
        inferred_relationships: list[dict[str, Any]] = []
        for rel in rels:
            confidence = 0.0
            if rel.constraint_name and rel.constraint_name.startswith("inferred_ref:"):
                try:
                    confidence = float(rel.constraint_name.split(":")[1])
                except Exception:
                    confidence = 0.0
            inferred_relationships.append(
                {
                    "source_field_path": rel.column_name,
                    "target_collection_name": rel.referenced_table,
                    "target_field_path": rel.referenced_column,
                    "relationship_type": "inferred_ref",
                    "confidence_score": confidence,
                }
            )

        serialized_profiles = [
            {
                "field_path": p.field_path,
                "inferred_data_type": p.inferred_data_type,
                "nested_depth": p.nested_depth,
                "is_array": p.is_array,
                "occurrence_percentage": p.occurrence_percentage,
                "schema_confidence": p.schema_confidence,
                "type_distribution": p.type_distribution,
            }
            for p in profiles
        ]
        schema_confidence = round(
            sum(p["schema_confidence"] for p in serialized_profiles) / max(1, len(serialized_profiles)),
            4,
        )
        return {
            "collection_name": collection,
            "sampled_documents": len(docs),
            "schema_confidence": schema_confidence,
            "fields": serialized_profiles,
            "sample_documents": docs[: min(5, len(docs))],
            "relationships": inferred_relationships,
        }
